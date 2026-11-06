"""Pydantic models used to validate everything the LLM returns before it is shown or stored."""
from pydantic import BaseModel, Field, field_validator

from app.services.log_processing import CATEGORIES

SEVERITIES = ["critical", "high", "medium", "low"]
RISK_LEVELS = ["high", "medium", "low"]


def _str_list(v, limit=8):
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [str(x).strip()[:500] for x in v if str(x).strip()][:limit]


class AnalysisResult(BaseModel):
    root_cause: str = Field(min_length=3, max_length=1500)
    category: str = "other"
    severity: str = "medium"
    summary: str = ""
    simple_explanation: str = ""
    suggested_resolution: list[str] = []

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        v = str(v or "other").strip().lower()
        return v if v in CATEGORIES else "other"

    @field_validator("severity", mode="before")
    @classmethod
    def _sev(cls, v):
        v = str(v or "medium").strip().lower()
        return v if v in SEVERITIES else "medium"

    @field_validator("suggested_resolution", mode="before")
    @classmethod
    def _steps(cls, v):
        return _str_list(v)

    @field_validator("root_cause", "summary", "simple_explanation", mode="before")
    @classmethod
    def _text(cls, v):
        return str(v or "").strip()[:1500]


class MemoryRecommendation(BaseModel):
    recommended_actions: list[str] = []
    memory_influence: str = ""
    used_memory: bool = False

    @field_validator("recommended_actions", mode="before")
    @classmethod
    def _steps(cls, v):
        return _str_list(v)


class RiskItem(BaseModel):
    title: str = ""
    detail: str = ""


class RiskResult(BaseModel):
    risk_level: str = "low"
    explanation: str = ""
    risks: list[RiskItem] = []
    preventive_actions: list[str] = []

    @field_validator("risk_level", mode="before")
    @classmethod
    def _lvl(cls, v):
        v = str(v or "low").strip().lower()
        return v if v in RISK_LEVELS else "medium"

    @field_validator("risks", mode="before")
    @classmethod
    def _risks(cls, v):
        if not isinstance(v, list):
            return []
        out = []
        for item in v[:8]:
            if isinstance(item, dict):
                out.append({"title": str(item.get("title", ""))[:200], "detail": str(item.get("detail", ""))[:600]})
            elif isinstance(item, str):
                out.append({"title": item[:200], "detail": ""})
        return out

    @field_validator("preventive_actions", mode="before")
    @classmethod
    def _steps(cls, v):
        return _str_list(v)
