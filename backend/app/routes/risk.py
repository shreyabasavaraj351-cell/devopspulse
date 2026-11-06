from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import analyzer
from app.ai.groq_client import AIUnavailable
from app.core.deps import get_org_user, get_user_project
from app.database.session import get_db
from app.memory.hindsight_service import MemoryUnavailable, bank_id, memory
from app.models.models import AnalysisHistory, Incident, User
from app.routes.deployments import clean_env, resolve_log_input
from app.schemas.ai import RiskResult
from app.services import log_processing as lp
from app.services.analysis_pipeline import incident_out, linked_incident_ids
from app.services.audit import log_action

router = APIRouter(prefix="/risk", tags=["risk"])

DISCLAIMER = "This is an AI-generated risk assessment based on the logs you provided and past incidents. It is not a guaranteed prediction."


@router.post("/analyze")
def analyze_risk(
    project_id: int = Form(...),
    deployment_name: str = Form(..., min_length=1, max_length=200),
    version: str = Form("", max_length=100),
    environment: str = Form("staging"),
    notes: str = Form("", max_length=2000),
    log_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(get_org_user),
    db: Session = Depends(get_db),
):
    project = get_user_project(db, user, project_id)
    raw = resolve_log_input(log_text, file)
    meta = {"name": deployment_name.strip(), "version": version.strip(), "environment": clean_env(environment)}

    prepared = lp.prepare(raw)
    sig = lp.detect(prepared)

    bank = bank_id(project.organization_id, project.id)
    query = f"{sig.category_hint} risk. {notes} " + " | ".join(sig.error_lines[:3] or [prepared[-300:]])
    memories, recall_status = [], "ok"
    try:
        memories = memory.recall(bank, query)
    except MemoryUnavailable:
        recall_status = "unavailable"

    ai_status = "ok"
    try:
        result = analyzer.assess_risk(meta, sig.excerpt, notes, memories)
    except AIUnavailable:
        ai_status = "fallback"
        level = "high" if sig.error_count else ("medium" if sig.warning_count > 5 else "low")
        result = RiskResult(
            risk_level=level,
            explanation="AI assessment was unavailable. This level is based only on error and warning counts in the log.",
            risks=[{"title": f"{sig.error_count} error line(s), {sig.warning_count} warning(s)", "detail": ""}] if (sig.error_count or sig.warning_count) else [],
            preventive_actions=lp.fallback_steps(sig.category_hint) if sig.error_count else [],
        )

    ids = linked_incident_ids(memories)
    related = []
    if ids:
        rows = db.scalars(select(Incident).where(Incident.id.in_(ids), Incident.project_id == project.id)).all()
        related = [incident_out(i) for i in rows]

    out = {
        **result.model_dump(),
        "related_incidents": related,
        "recalled_memories": memories,
        "ai_status": ai_status,
        "memory_status": recall_status,
        "disclaimer": DISCLAIMER,
    }
    db.add(AnalysisHistory(organization_id=project.organization_id, project_id=project.id, kind="risk", risk_level=result.risk_level, result=out))
    log_action(db, project.organization_id, user.id, "memory.recall",
               {"purpose": "risk", "hits": len(memories), "status": recall_status}, project.id)
    log_action(db, project.organization_id, user.id, "risk.analyze", {"risk_level": result.risk_level}, project.id)
    db.commit()
    return out
