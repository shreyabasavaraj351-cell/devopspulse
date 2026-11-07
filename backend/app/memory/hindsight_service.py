"""Thin wrapper around the Hindsight memory service (retain / recall / reflect).

One memory bank per organisation+project, so retrieval can never cross tenants.
NOTE: written against the hindsight-client Python SDK; confirm method names/args against the
version you install (`pip show hindsight-client`) and the Hindsight docs.
"""
import logging

import httpx

from app.core.config import settings

log = logging.getLogger("devopspulse.memory")


class MemoryUnavailable(Exception):
    pass


def _error_label(exc: Exception) -> str:
    """Log only safe provider diagnostics; never log response bodies or credentials."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"{type(exc).__name__} (HTTP {status})" if status else type(exc).__name__


def bank_id(org_id: int, project_id: int) -> str:
    return f"pm-org{org_id}-proj{project_id}"


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class MemoryService:
    def __init__(self):
        self._client = None
        self._banks: set[str] = set()

    def _c(self):
        if self._client is None:
            try:
                from hindsight_client import Hindsight

                kwargs = {"base_url": settings.hindsight_base_url}
                if settings.hindsight_api_key:
                    kwargs["api_key"] = settings.hindsight_api_key
                self._client = Hindsight(**kwargs)
            except Exception as exc:
                raise MemoryUnavailable(f"Hindsight client unavailable: {type(exc).__name__}") from exc
        return self._client

    def retain(self, bank: str, content: str, context: str | None = None) -> None:
        try:
            self._c().retain(bank_id=bank, content=content, context=context or "deployment incident")
        except MemoryUnavailable:
            raise
        except Exception as exc:
            log.warning("Hindsight retain failed: %s", _error_label(exc))
            raise MemoryUnavailable("retain failed") from exc

    def recall(self, bank: str, query: str, max_results: int = 5) -> list[dict]:
        try:
            client = self._c()
            if bank not in self._banks:
                client.create_bank(bank_id=bank)
                self._banks.add(bank)
            resp = client.recall(bank_id=bank, query=query[:1000])
        except MemoryUnavailable:
            raise
        except Exception as exc:
            log.warning("Hindsight recall failed: %s", _error_label(exc))
            raise MemoryUnavailable("recall failed") from exc
        results = _get(resp, "results", resp) or []
        out = []
        for r in list(results)[:max_results]:
            text = _get(r, "text") or _get(r, "content") or str(r)
            out.append({"text": str(text)[:1500]})
        return out

    def reflect(self, bank: str, query: str) -> str | None:
        try:
            resp = self._c().reflect(bank_id=bank, query=query[:1000])
        except MemoryUnavailable:
            raise
        except Exception as exc:
            log.warning("Hindsight reflect failed: %s", _error_label(exc))
            raise MemoryUnavailable("reflect failed") from exc
        text = _get(resp, "text") or (resp if isinstance(resp, str) else None)
        return str(text)[:3000] if text else None

    def status(self) -> dict:
        try:
            r = httpx.get(settings.hindsight_base_url.rstrip("/") + "/health", timeout=3.0)
            ok = r.status_code == 200
        except Exception:
            ok = False
        return {"reachable": ok, "api_key_set": bool(settings.hindsight_api_key)}


memory = MemoryService()
