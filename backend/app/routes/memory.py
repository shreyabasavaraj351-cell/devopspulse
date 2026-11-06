from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_org_user, get_user_project
from app.database.session import get_db
from app.memory.hindsight_service import MemoryUnavailable, bank_id, memory
from app.models.models import AuditLog, Incident, Project, User
from app.services.analysis_pipeline import incident_out, linked_incident_ids
from app.services.audit import log_action

router = APIRouter(prefix="/memory", tags=["memory"])

MEMORY_ACTIONS = ("memory.retain", "memory.retain_outcome", "memory.recall", "memory.retain_failed", "memory.explore")


class RecallIn(BaseModel):
    project_id: int
    query: str = Field(min_length=2, max_length=1000)


@router.get("")
def memory_activity(project_id: int, user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    """Timeline of what the agent retained and recalled, plus incidents whose advice was shaped by memory."""
    project = get_user_project(db, user, project_id)
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.project_id == project.id, AuditLog.organization_id == user.organization_id, AuditLog.action.in_(MEMORY_ACTIONS))
        .order_by(AuditLog.id.desc())
        .limit(100)
    ).all()
    influenced = db.scalars(
        select(Incident).where(Incident.project_id == project.id, Incident.memory_influenced.is_(True)).order_by(Incident.id.desc()).limit(20)
    ).all()
    retained = db.scalars(
        select(Incident).where(Incident.project_id == project.id, Incident.memory_status == "retained")
    ).all()
    return {
        "bank_id": bank_id(project.organization_id, project.id),
        "service": memory.status(),
        "retained_incidents": len(retained),
        "timeline": [
            {"id": l.id, "action": l.action, "detail": l.detail, "created_at": l.created_at} for l in logs
        ],
        "influenced_incidents": [
            {**incident_out(i), "memory_explanation": i.memory_explanation, "recalled_incident_ids": i.recalled_incident_ids}
            for i in influenced
        ],
    }


@router.post("/recall")
def recall(body: RecallIn, user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    project: Project = get_user_project(db, user, body.project_id)
    bank = bank_id(project.organization_id, project.id)
    try:
        memories = memory.recall(bank, body.query)
        status = "ok"
    except MemoryUnavailable:
        memories, status = [], "unavailable"

    ids = linked_incident_ids(memories)
    related = []
    if ids:
        rows = db.scalars(select(Incident).where(Incident.id.in_(ids), Incident.project_id == project.id)).all()
        related = [incident_out(i) for i in rows]

    log_action(db, project.organization_id, user.id, "memory.explore", {"query": body.query[:200], "hits": len(memories), "status": status}, project.id)
    db.commit()
    return {"status": status, "memories": memories, "related_incidents": related}
