"""The memory-driven agent loop:

logs -> redact/scan -> Groq analysis -> Hindsight recall -> Groq memory-aware recommendation
     -> save incident -> Hindsight retain (as UNVERIFIED) ... later: user feedback -> retain verified outcome.
"""
import re

from sqlalchemy.orm import Session

from app.ai import analyzer
from app.ai.groq_client import AIUnavailable
from app.memory.hindsight_service import MemoryUnavailable, bank_id, memory
from app.models.models import AnalysisHistory, Deployment, Feedback, Incident, Project, Resolution, User
from app.schemas.ai import AnalysisResult
from app.services import log_processing as lp
from app.services.audit import log_action

_INCIDENT_REF = re.compile(r"[Ii]ncident #(\d+)")


def linked_incident_ids(memories: list[dict]) -> list[int]:
    ids = []
    for m in memories:
        for found in _INCIDENT_REF.findall(m["text"]):
            if int(found) not in ids:
                ids.append(int(found))
    return ids


def incident_out(i: Incident, detail: bool = False) -> dict:
    out = {
        "id": i.id,
        "title": i.title,
        "category": i.category,
        "severity": i.severity,
        "root_cause": i.root_cause,
        "status": i.status,
        "project_id": i.project_id,
        "deployment_id": i.deployment_id,
        "deployment_name": i.deployment.name if i.deployment else None,
        "environment": i.deployment.environment if i.deployment else None,
        "created_at": i.created_at,
        "memory_status": i.memory_status,
        "memory_influenced": i.memory_influenced,
    }
    if detail:
        out.update(
            summary=i.summary,
            simple_explanation=i.simple_explanation,
            error_lines=i.error_lines,
            ai_status=i.ai_status,
            memory_explanation=i.memory_explanation,
            recalled_incident_ids=i.recalled_incident_ids,
            version=i.deployment.version if i.deployment else None,
            resolutions=[
                {"id": r.id, "text": r.text, "verified": r.verified, "source": r.source, "created_at": r.created_at}
                for r in i.resolutions
            ],
            feedback=[
                {"id": f.id, "outcome": f.outcome, "followed_suggestion": f.followed_suggestion, "notes": f.notes, "created_at": f.created_at}
                for f in i.feedback
            ],
        )
    return out


def deployment_out(d: Deployment) -> dict:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "name": d.name,
        "version": d.version,
        "environment": d.environment,
        "status": d.status,
        "error_count": d.error_count,
        "warning_count": d.warning_count,
        "created_at": d.created_at,
    }


def _recall_query(analysis: AnalysisResult, sig: lp.LogSignals) -> str:
    return f"{analysis.category} failure: {analysis.root_cause}. " + " | ".join(sig.error_lines[:3])


def _retain_text(inc: Incident, project: Project, dep: Deployment, analysis: AnalysisResult, steps: list[str], sig) -> str:
    return (
        f"Incident #{inc.id} in project '{project.name}' ({dep.environment}), deployment '{dep.name}' "
        f"version {dep.version or 'unknown'}. Category: {analysis.category}. Severity: {analysis.severity}. "
        f"Root cause (AI-assessed, not yet verified by a user): {analysis.root_cause} "
        f"Key errors: {' | '.join(sig.error_lines[:3])} "
        f"Suggested resolution (UNVERIFIED, no outcome confirmed yet): {'; '.join(steps)}"
    )


def run_analysis(db: Session, user: User, project: Project, name: str, version: str, environment: str, raw_log: str) -> dict:
    prepared = lp.prepare(raw_log)
    sig = lp.detect(prepared)
    meta = {"name": name, "version": version, "environment": environment}

    dep = Deployment(
        organization_id=project.organization_id,
        project_id=project.id,
        name=name,
        version=version,
        environment=environment,
        status="failed" if sig.has_failure else "success",
        error_count=sig.error_count,
        warning_count=sig.warning_count,
        log_excerpt=sig.excerpt,
        created_by=user.id,
    )
    db.add(dep)
    db.flush()

    if not sig.has_failure:
        log_action(db, project.organization_id, user.id, "deployment.analyze", {"deployment_id": dep.id, "status": "success"}, project.id)
        db.commit()
        return {
            "deployment": deployment_out(dep),
            "incident": None,
            "message": "No errors or failure patterns detected in this log, so no incident was created.",
            "line_count": sig.line_count,
            "warning_count": sig.warning_count,
        }

    # 1. Groq analysis (falls back to a heuristic result if Groq is unavailable)
    ai_status = "ok"
    try:
        analysis = analyzer.analyze_failure(meta, sig.excerpt, sig.category_hint)
    except AIUnavailable:
        ai_status = "fallback"
        first = sig.error_lines[0] if sig.error_lines else "Failure detected in log"
        analysis = AnalysisResult(
            root_cause=f"Likely {sig.category_hint} issue. First error: {first}"[:1500],
            category=sig.category_hint,
            severity="medium",
            summary="AI analysis was unavailable, so this is a basic pattern-based result.",
            simple_explanation="The log contains error lines. Review them with the suggested checks below.",
            suggested_resolution=lp.fallback_steps(sig.category_hint),
        )

    # 2. Hindsight recall (before retaining this incident, so it cannot recall itself)
    bank = bank_id(project.organization_id, project.id)
    memories: list[dict] = []
    recall_status = "ok"
    try:
        memories = memory.recall(bank, _recall_query(analysis, sig))
    except MemoryUnavailable:
        recall_status = "unavailable"

    # 3. Memory-aware recommendation (only when memories exist)
    steps = analysis.suggested_resolution
    influenced, influence_text = False, ""
    if memories and ai_status == "ok":
        try:
            rec = analyzer.recommend_with_memory(meta, analysis, memories)
            if rec.recommended_actions:
                steps = rec.recommended_actions
            influenced, influence_text = rec.used_memory, rec.memory_influence
        except AIUnavailable:
            ai_status = "partial"
            influence_text = "Past incidents were recalled, but Groq was unavailable to refine the recommendation."
    elif memories:
        influence_text = "Related past incidents were recalled, but AI was unavailable to refine the advice."

    recalled_ids = linked_incident_ids(memories)

    incident = Incident(
        organization_id=project.organization_id,
        project_id=project.id,
        deployment_id=dep.id,
        title=f"{analysis.category.title()} failure in {name}"[:300],
        category=analysis.category,
        severity=analysis.severity,
        root_cause=analysis.root_cause,
        summary=analysis.summary,
        simple_explanation=analysis.simple_explanation,
        error_lines=sig.error_lines[:10],
        status="open",
        ai_status=ai_status,
        memory_influenced=influenced,
        memory_explanation=influence_text,
        recalled_incident_ids=recalled_ids,
    )
    db.add(incident)
    db.flush()
    db.add(Resolution(incident_id=incident.id, text="\n".join(steps), verified=False, source="ai_suggested"))
    db.add(
        AnalysisHistory(
            organization_id=project.organization_id,
            project_id=project.id,
            deployment_id=dep.id,
            kind="analysis",
            result={"analysis": analysis.model_dump(), "steps": steps, "ai_status": ai_status},
        )
    )
    log_action(db, project.organization_id, user.id, "memory.recall",
               {"incident_id": incident.id, "hits": len(memories), "status": recall_status, "influenced": influenced}, project.id)

    # 4. Hindsight retain: stored as an UNVERIFIED suggestion; learning from success waits for user feedback
    try:
        memory.retain(bank, _retain_text(incident, project, dep, analysis, steps, sig), context="deployment incident")
        incident.memory_status = "retained"
        log_action(db, project.organization_id, user.id, "memory.retain",
                   {"incident_id": incident.id, "verified": False, "summary": analysis.root_cause[:200]}, project.id)
    except MemoryUnavailable:
        incident.memory_status = "failed"
        log_action(db, project.organization_id, user.id, "memory.retain_failed", {"incident_id": incident.id}, project.id)

    log_action(db, project.organization_id, user.id, "deployment.analyze", {"deployment_id": dep.id, "incident_id": incident.id, "status": "failed"}, project.id)
    db.commit()
    db.refresh(incident)

    related = [{"id": r.id, "title": r.title, "root_cause": r.root_cause, "status": r.status} for r in _load_incidents(db, project, recalled_ids)]
    return {
        "deployment": deployment_out(dep),
        "incident": incident_out(incident, detail=True),
        "analysis": analysis.model_dump(),
        "recommendation": {
            "actions": steps,
            "used_memory": influenced,
            "memory_influence": influence_text,
            "recalled_memories": memories,
            "related_incidents": related,
        },
        "ai_status": ai_status,
        "memory": {"recall": recall_status, "retain": incident.memory_status},
        "note": "Suggested resolutions are unverified. Confirm the outcome on the incident page so the agent can learn from it.",
    }


def _load_incidents(db: Session, project: Project, ids: list[int]) -> list[Incident]:
    if not ids:
        return []
    rows = db.query(Incident).filter(Incident.id.in_(ids), Incident.project_id == project.id).all()
    return rows


def apply_feedback(db: Session, user: User, incident: Incident, outcome: str, followed: bool, notes: str) -> dict:
    project = db.get(Project, incident.project_id)
    db.add(Feedback(incident_id=incident.id, user_id=user.id, outcome=outcome, followed_suggestion=followed, notes=notes))
    incident.status = outcome if outcome in ("resolved", "partially_resolved") else "open"

    verified_text = None
    if outcome == "resolved":
        if notes.strip():
            verified_text = notes.strip()
        elif followed and incident.resolutions:
            verified_text = incident.resolutions[0].text
        if verified_text:
            db.add(Resolution(incident_id=incident.id, text=verified_text, verified=True, source="user_confirmed"))

    bank = bank_id(project.organization_id, project.id)
    content = (
        f"Outcome update for Incident #{incident.id} ({incident.category}, root cause: {incident.root_cause[:300]}). "
        f"User reported outcome: {outcome.replace('_', ' ')}. Followed the suggested resolution: {'yes' if followed else 'no'}. "
    )
    if verified_text:
        content += f"VERIFIED resolution confirmed by the user: {verified_text} "
    elif outcome == "not_resolved":
        content += "The suggested resolution did NOT fix this incident. "
    if notes.strip() and not verified_text:
        content += f"User notes: {notes.strip()[:500]}"

    memory_status = "retained"
    try:
        memory.retain(bank, content, context="incident outcome feedback")
        log_action(db, project.organization_id, user.id, "memory.retain_outcome",
                   {"incident_id": incident.id, "outcome": outcome, "verified": bool(verified_text)}, project.id)
    except MemoryUnavailable:
        memory_status = "failed"
        log_action(db, project.organization_id, user.id, "memory.retain_failed", {"incident_id": incident.id, "outcome": outcome}, project.id)

    log_action(db, project.organization_id, user.id, "incident.feedback", {"incident_id": incident.id, "outcome": outcome}, project.id)
    db.commit()
    db.refresh(incident)
    return {"incident": incident_out(incident, detail=True), "memory_status": memory_status, "verified": bool(verified_text)}
