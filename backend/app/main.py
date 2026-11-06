import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.database.session import Base, engine
from app.models import models  # noqa: F401  (registers tables)
from app.routes import assistant, auth, dashboard, deployments, incidents, memory, onboarding, risk, settings as settings_routes

logging.basicConfig(level=logging.INFO)
if settings.secret_key.startswith("dev-insecure") or settings.secret_key.startswith("change-me"):
    logging.getLogger("devopspulse").warning("SECRET_KEY is a placeholder. Set a long random value in .env before deploying.")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DevOpsPulse",
    description="DevOpsPulse is an AI DevOps assistant for deployment analysis and incident memory.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    auth.router, onboarding.router, dashboard.router, deployments.router, incidents.router,
    memory.router, risk.router, assistant.router, settings_routes.router,
):
    app.include_router(r)


@app.get("/health")
def health():
    return {"status": "ok", "service": "DevOpsPulse"}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    @app.middleware("http")
    async def serve_frontend_on_api_path_collisions(request, call_next):
        frontend_paths = {"/incidents", "/memory"}
        accepts_html = "text/html" in request.headers.get("accept", "")
        if request.method == "GET" and request.url.path in frontend_paths and accepts_html:
            return FileResponse(frontend_dist / "index.html")
        return await call_next(request)

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        candidate = (frontend_dist / path).resolve()
        try:
            candidate.relative_to(frontend_dist)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(candidate if candidate.is_file() else frontend_dist / "index.html")
