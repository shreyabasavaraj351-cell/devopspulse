import json
import re

from app.core.config import settings


class AIUnavailable(Exception):
    """Raised when Groq is not configured or a request to it fails."""


def chat(messages: list[dict], json_mode: bool = False, max_tokens: int = 1200, temperature: float = 0.2) -> str:
    if not settings.groq_api_key:
        raise AIUnavailable("GROQ_API_KEY is not configured")
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key, timeout=45.0)
        kwargs = dict(
            model=settings.groq_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    except AIUnavailable:
        raise
    except Exception as exc:  # network errors, rate limits, SDK missing, etc.
        raise AIUnavailable(f"Groq request failed: {type(exc).__name__}") from exc


def chat_json(messages: list[dict], max_tokens: int = 1200) -> dict:
    raw = chat(messages, json_mode=True, max_tokens=max_tokens)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise AIUnavailable("Groq returned invalid JSON")
