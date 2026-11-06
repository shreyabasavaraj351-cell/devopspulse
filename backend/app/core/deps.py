from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.session import get_db
from app.models.models import Project, User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if creds is None:
        raise unauthorized
    sub = decode_token(creds.credentials)
    if not sub or not sub.isdigit():
        raise unauthorized
    user = db.get(User, int(sub))
    if user is None:
        raise unauthorized
    return user


def get_org_user(user: User = Depends(get_current_user)) -> User:
    if user.organization_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Complete onboarding first")
    return user


def get_user_project(db: Session, user: User, project_id: int) -> Project:
    """Org isolation: a project is only visible to members of its organization."""
    project = db.get(Project, project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project
