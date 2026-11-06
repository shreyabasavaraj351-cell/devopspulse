"""Reading, redacting, cleaning and scanning deployment logs."""
import re
from dataclasses import dataclass, field

from fastapi import HTTPException, UploadFile

CATEGORIES = [
    "dependency", "build", "test", "configuration", "permissions",
    "network", "database", "resource", "timeout", "container", "other",
]

ALLOWED_EXTENSIONS = {".log", ".txt", ".out"}

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(postgres(?:ql)?|mysql|mongodb|redis|amqp)://([^:\s/]+):([^@\s]+)@"), r"\1://\2:[REDACTED]@"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"), "[REDACTED_KEY]"),
    (
        re.compile(r"(?i)\b(api[_-]?key|secret|token|passwd|password|pwd)\b(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"),
        r"\1\2[REDACTED]",
    ),
]

_ERROR_RE = re.compile(
    r"(\b(error|fatal|exception|traceback|failed|failure|panic|denied|refused|timed?[ -]?out|"
    r"oom|out of memory|killed|segfault|cannot|could not|unable to|no such file|not found|"
    r"exit(?:ed)?(?: with)?(?: code| status)? [1-9]\d*)\b|\bERR!)",
    re.I,
)
_NOT_ERROR_RE = re.compile(r"\b(0|no) (failed|failures?|errors?)\b", re.I)
_WARN_RE = re.compile(r"\b(warn(?:ing)?|deprecated)\b", re.I)

_CATEGORY_RULES = [
    ("resource", re.compile(r"out of memory|oom|killed|no space left|disk full|heap", re.I)),
    ("permissions", re.compile(r"permission denied|access denied|forbidden|unauthori[sz]ed|403|401|iam", re.I)),
    ("database", re.compile(r"database|postgres|mysql|sql|migration|connection pool|deadlock|relation .* does not exist", re.I)),
    ("timeout", re.compile(r"timed?[ -]?out|deadline exceeded|etimedout", re.I)),
    ("network", re.compile(r"connection refused|econnrefused|dns|unreachable|name resolution|econnreset|tls|ssl", re.I)),
    ("container", re.compile(r"docker|image pull|imagepullbackoff|crashloopbackoff|kubernetes|kubectl|pod ", re.I)),
    ("dependency", re.compile(r"npm err|pip|module not found|no matching distribution|could not resolve|cannot find module|dependency|version conflict", re.I)),
    ("test", re.compile(r"assertion|test(s)? failed|failing test|pytest|jest|\bFAIL\b", re.I)),
    ("configuration", re.compile(r"env(ironment)? variable|missing config|invalid config|yaml|\.env|not set|undefined variable", re.I)),
    ("build", re.compile(r"compil|syntax error|build failed|webpack|tsc|linker|cannot resolve symbol", re.I)),
]

_FALLBACK_STEPS = {
    "resource": ["Check memory/disk limits for the build or runtime.", "Increase resource limits or reduce parallelism, then redeploy."],
    "permissions": ["Verify the deploy credentials or service account permissions.", "Check file and registry access rules for the failing step."],
    "database": ["Verify the database is reachable and credentials are valid.", "Review the latest migration for errors and re-run it in staging."],
    "timeout": ["Check the health and latency of the service that timed out.", "Raise the timeout only after confirming the dependency is healthy."],
    "network": ["Confirm DNS, firewall and security-group rules for the target host.", "Retry once the dependency is reachable."],
    "container": ["Check image name, tag and registry access.", "Inspect container or pod events for the exact failure."],
    "dependency": ["Pin or update the failing dependency version.", "Clear caches and reinstall dependencies cleanly."],
    "test": ["Re-run the failing test locally to reproduce.", "Fix the failing assertion before deploying."],
    "configuration": ["Check that all required environment variables and config files are set.", "Compare config against a known working environment."],
    "build": ["Fix the compile or build error shown in the log.", "Rebuild from a clean workspace."],
    "other": ["Review the error lines in the log and reproduce the failure in a non-production environment."],
}


@dataclass
class LogSignals:
    line_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    error_lines: list[str] = field(default_factory=list)
    category_hint: str = "other"
    excerpt: str = ""

    @property
    def has_failure(self) -> bool:
        return self.error_count > 0


def read_upload(file: UploadFile, max_bytes: int) -> str:
    name = (file.filename or "").lower()
    if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(400, "Unsupported file type. Upload a .log, .txt or .out file.")
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large (max {max_bytes // 1024} KB).")
    if b"\x00" in data:
        raise HTTPException(400, "File looks binary, not a text log.")
    return data.decode("utf-8", errors="replace")


def redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def prepare(raw: str) -> str:
    """Redact secrets, strip ANSI codes, normalise line endings, collapse repeated lines."""
    text = redact(_ANSI.sub("", raw)).replace("\r\n", "\n").replace("\r", "\n")
    out, prev, repeats = [], None, 0
    for line in text.split("\n"):
        line = line.rstrip()
        if line and line == prev:
            repeats += 1
            continue
        if repeats:
            out.append(f"  [previous line repeated {repeats} more times]")
            repeats = 0
        out.append(line)
        prev = line
    if repeats:
        out.append(f"  [previous line repeated {repeats} more times]")
    return "\n".join(out).strip()


def detect(text: str) -> LogSignals:
    lines = text.split("\n") if text else []
    sig = LogSignals(line_count=len(lines))
    error_idx = []
    for i, line in enumerate(lines):
        if _NOT_ERROR_RE.search(line):
            continue
        if _ERROR_RE.search(line):
            sig.error_count += 1
            error_idx.append(i)
            if len(sig.error_lines) < 40:
                sig.error_lines.append(line.strip()[:400])
        elif _WARN_RE.search(line):
            sig.warning_count += 1

    keep = set()
    for i in error_idx[:25]:
        keep.update(range(max(0, i - 2), min(len(lines), i + 2)))
    if not keep:
        keep = set(range(max(0, len(lines) - 40), len(lines)))
    excerpt = "\n".join(lines[i] for i in sorted(keep))
    sig.excerpt = excerpt[:8000]

    probe = "\n".join(sig.error_lines) or excerpt
    for category, rx in _CATEGORY_RULES:
        if rx.search(probe):
            sig.category_hint = category
            break
    return sig


def fallback_steps(category: str) -> list[str]:
    return _FALLBACK_STEPS.get(category, _FALLBACK_STEPS["other"])
