from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_org_user
from app.database.session import get_db
from app.models.models import Organization, Project, User
from app.routes.auth import user_out
from app.schemas.auth import OnboardingIn, ProjectIn
from app.services.audit import log_action

router = APIRouter(tags=["onboarding"])


def project_out(p: Project) -> dict:
    return {"id": p.id, "name": p.name, "environment": p.environment, "created_at": p.created_at}


@router.post("/onboarding", status_code=201)
def onboard(body: OnboardingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.organization_id is not None:
        raise HTTPException(409, "Onboarding already completed")
    org = Organization(name=body.organization_name.strip())
    db.add(org)
    db.flush()
    user.organization_id = org.id
    project = Project(organization_id=org.id, name=body.project_name.strip(), environment=body.environment)
    db.add(project)
    db.flush()
    log_action(db, org.id, user.id, "onboarding.complete", {"project_id": project.id}, project_id=project.id)
    db.commit()
    db.refresh(user)
    return {"user": user_out(user), "project": project_out(project)}


@router.get("/projects")
def list_projects(user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Project).where(Project.organization_id == user.organization_id).order_by(Project.id)).all()
    return [project_out(p) for p in rows]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    project = Project(organization_id=user.organization_id, name=body.project_name.strip(), environment=body.environment)
    db.add(project)
    db.flush()
    log_action(db, user.organization_id, user.id, "project.create", {"project_id": project.id}, project_id=project.id)
    db.commit()
    return project_out(project)
