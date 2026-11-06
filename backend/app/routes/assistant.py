from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import analyzer
from app.ai.groq_client import AIUnavailable
from app.core.deps import get_org_user, get_user_project
from app.database.session import get_db
from app.memory.hindsight_service import MemoryUnavailable, bank_id, memory
from app.models.models import Incident, User
from app.services.analysis_pipeline import incident_out, linked_incident_ids
from app.services.audit import log_action

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatIn(BaseModel):
    project_id: int
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict] = []


def _keyword_incidents(db: Session, project_id: int, message: str, limit: int = 5) -> list[Incident]:
    words = [w for w in {w.strip(".,?!:;()\"'").lower() for w in message.split()} if len(w) > 3][:8]
    if not words:
        return []
    conds = []
    for w in words:
        like = f"%{w}%"
        conds += [Incident.root_cause.ilike(like), Incident.title.ilike(like), Incident.category.ilike(like)]
    return list(db.scalars(select(Incident).where(Incident.project_id == project_id, or_(*conds)).order_by(Incident.id.desc()).limit(limit)).all())


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    project = get_user_project(db, user, body.project_id)
    bank = bank_id(project.organization_id, project.id)

    memories, reflection, memory_status = [], None, "ok"
    try:
        memories = memory.recall(bank, body.message)
        if memories:
            reflection = memory.reflect(bank, body.message)
    except MemoryUnavailable:
        memory_status = "unavailable"

    ids = linked_incident_ids(memories)
    found = {}
    if ids:
        for i in db.scalars(select(Incident).where(Incident.id.in_(ids), Incident.project_id == project.id)).all():
            found[i.id] = i
    for i in _keyword_incidents(db, project.id, body.message):
        found.setdefault(i.id, i)
    incidents = list(found.values())[:6]

    incident_ctx = [
        {
            "id": i.id, "title": i.title, "category": i.category, "severity": i.severity, "root_cause": i.root_cause,
            "status": i.status,
            "verified_resolution": next((r.text for r in i.resolutions if r.verified), None),
            "suggested_resolution_unverified": next((r.text for r in i.resolutions if not r.verified), None),
        }
        for i in incidents
    ]

    try:
        reply = analyzer.answer_question(body.message, memories, reflection, incident_ctx, body.history)
        ai_status = "ok"
    except AIUnavailable:
        ai_status = "unavailable"
        reply = "The AI service is unavailable right now, so I can't write an answer. The related incidents I found are listed below."

    log_action(db, project.organization_id, user.id, "memory.recall",
               {"purpose": "assistant", "hits": len(memories), "status": memory_status}, project.id)
    db.commit()
    return {
        "reply": reply,
        "used_memory": bool(memories),
        "references": [incident_out(i) for i in incidents],
        "memory_status": memory_status,
        "ai_status": ai_status,
    }
