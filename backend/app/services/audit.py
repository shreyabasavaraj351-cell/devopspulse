from sqlalchemy.orm import Session

from app.models.models import AuditLog


def log_action(db: Session, org_id, user_id, action: str, detail: dict | None = None, project_id=None):
    db.add(
        AuditLog(
            organization_id=org_id,
            user_id=user_id,
            project_id=project_id,
            action=action,
            detail=detail or {},
        )
    )
