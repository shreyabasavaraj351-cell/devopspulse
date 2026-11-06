from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.database.session import get_db
from app.memory.hindsight_service import memory
from app.models.models import Project, User
from app.routes.auth import user_out
from app.schemas.auth import ChangePasswordIn, ProfileUpdateIn
from app.services.audit import log_action

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/integrations")
def integrations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only booleans and status are returned. Keys and URLs with credentials are never sent to the frontend.
    projects = []
    if user.organization_id:
        projects = db.scalars(select(Project).where(Project.organization_id == user.organization_id)).all()
    return {
        "groq": {"configured": bool(settings.groq_api_key), "model": settings.groq_model},
        "hindsight": memory.status(),
        "memory_banks": [{"project_id": p.id, "project": p.name, "bank": f"pm-org{p.organization_id}-proj{p.id}"} for p in projects],
        "database": "postgresql" if settings.database_url.startswith("postgres") else "sqlite",
    }


@router.patch("/profile")
def update_profile(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.full_name:
        user.full_name = body.full_name.strip()
    if body.email and body.email.lower() != user.email:
        if db.scalar(select(User).where(User.email == body.email.lower())):
            raise HTTPException(409, "That email is already in use")
        user.email = body.email.lower()
    log_action(db, user.organization_id, user.id, "settings.profile_update")
    db.commit()
    return user_out(user)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    user.hashed_password = hash_password(body.new_password)
    log_action(db, user.organization_id, user.id, "settings.change_password")
    db.commit()
    return {"message": "Password changed"}
