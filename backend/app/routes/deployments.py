from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_org_user, get_user_project
from app.database.session import get_db
from app.models.models import Deployment, Incident, User
from app.services import log_processing as lp
from app.services.analysis_pipeline import deployment_out, incident_out, run_analysis

router = APIRouter(prefix="/deployments", tags=["deployments"])

ENVIRONMENTS = ("development", "testing", "staging")


def resolve_log_input(log_text: str | None, file: UploadFile | None) -> str:
    """Accept either pasted text or an uploaded file, with size and type validation."""
    if file is not None and file.filename:
        text = lp.read_upload(file, settings.max_upload_bytes)
    elif log_text and log_text.strip():
        if len(log_text.encode()) > settings.max_upload_bytes:
            raise HTTPException(413, f"Log too large (max {settings.max_upload_bytes // 1024} KB).")
        text = log_text
    else:
        raise HTTPException(400, "Provide a log file or paste log text.")
    if not text.strip():
        raise HTTPException(400, "The log is empty.")
    return text


def clean_env(environment: str) -> str:
    env = environment.lower().strip()
    if env not in ENVIRONMENTS:
        raise HTTPException(400, "Environment must be development, testing or staging.")
    return env


@router.post("/analyze")
def analyze(
    project_id: int = Form(...),
    deployment_name: str = Form(..., min_length=1, max_length=200),
    version: str = Form("", max_length=100),
    environment: str = Form("development"),
    log_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(get_org_user),
    db: Session = Depends(get_db),
):
    project = get_user_project(db, user, project_id)
    raw = resolve_log_input(log_text, file)
    return run_analysis(db, user, project, deployment_name.strip(), version.strip(), clean_env(environment), raw)


@router.get("")
def list_deployments(
    project_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    user: User = Depends(get_org_user),
    db: Session = Depends(get_db),
):
    q = select(Deployment).where(Deployment.organization_id == user.organization_id)
    if project_id:
        q = q.where(Deployment.project_id == project_id)
    if status in ("success", "failed"):
        q = q.where(Deployment.status == status)
    rows = db.scalars(q.order_by(Deployment.id.desc()).limit(min(limit, 200))).all()
    return [deployment_out(d) for d in rows]


@router.get("/{deployment_id}")
def get_deployment(deployment_id: int, user: User = Depends(get_org_user), db: Session = Depends(get_db)):
    d = db.get(Deployment, deployment_id)
    if not d or d.organization_id != user.organization_id:
        raise HTTPException(404, "Deployment not found")
    inc = db.scalar(select(Incident).where(Incident.deployment_id == d.id))
    return {
        **deployment_out(d),
        "log_excerpt": d.log_excerpt,
        "incident": incident_out(inc, detail=True) if inc else None,
    }
