from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_org_user
from app.database.session import get_db
from app.models.models import Incident, User
from app.services.analysis_pipeline import apply_feedback, incident_out

router = APIRouter(prefix="/incidents", tags=["incidents"])


class FeedbackIn(BaseModel):
    outcome: str  # resolved | partially_resolved | not_resolved
    followed_suggestion: bool = True
    notes: str = ""


def _get(db: Session, user: User, incident_id: int) -> Incident:
    inc = db.get(Incident, incident_id)
    if not inc or inc.organization_id != user.organization_id:
        raise HTTPException(404, "Incident not found")
    return inc


@router.get("")
def list_incidents(
    project_id: int | None = None,
    severity: str | None = None,
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    user: User = Depends(get_org_user),
    db: Session = Depends(get_db),
):
    stmt = select(Incident).where(Incident.organization_id == user.organization_id)
    if project_id:
        stmt = stmt.where(Incident.project_id == project_id)
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if category:
        stmt = stmt.where(Incident.category == category)
    if status:
        stmt = stmt.where(Incident.status == status)
    if q:
        like = f"%{q.strip()[:100]}%"
        stmt = stmt.where(or_(Incident.title.ilike(like), Incident.root_cause.ilike(like), Incident.summary.ilike(like)))
    rows = db.scalars(stmt.order_by(Incident.id.desc()).limit(min(limit, 300))).all()
    return [incident_out(i) for i in rows]


@router.get("/{incident_id}")
def get_incident(incident_id: int, user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    return incident_out(_get(db, user, incident_id), detail=True)


@router.post("/{incident_id}/feedback")
def submit_feedback(incident_id: int, body: FeedbackIn, user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    if body.outcome not in ("resolved", "partially_resolved", "not_resolved"):
        raise HTTPException(400, "outcome must be resolved, partially_resolved or not_resolved")
    incident = _get(db, user, incident_id)
    return apply_feedback(db, user, incident, body.outcome, body.followed_suggestion, body.notes[:2000])
