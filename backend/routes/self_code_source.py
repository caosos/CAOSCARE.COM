"""Read-only, bounded access to the CAOSCARE source Aria is allowed to see.

Knowledge access only. Nothing here writes, runs, or lists anything outside
the approved allow-list; there is no shell and no general filesystem access.
The allow-list is a fixed set of repo-relative globs covering the code and
docs that make Room 214 Aria what she is (realtime session, tools, memory,
wake, room page, this capability itself, and the product docs).

Hard denies (checked on every path, before any read):
  - anything not on the allow-list (so .env*, keys, credentials, Mongo
    strings, raw DB files, /proc, /etc, other homes are never reachable);
  - absolute paths, "..", backslashes, NUL, empty parts;
  - symlinks anywhere in the path (the resolved file must be exactly the
    checkout path), files outside the checkout, non-regular files;
  - names that look like a secret store even if a glob matched them;
  - binary content, files over SIZE_CAP.
Reads are line-range bounded (MAX_LINES); searches are literal, case-
insensitive, capped. Lines that look like credentials are redacted
defensively even though no approved file should contain one.

Revision truth: `revision()` reports the checkout's HEAD (git, read-only,
fixed argv, no shell) and the backend's loaded SHA (CAOSCARE_RUNTIME_SHA,
set by the restart/deploy scripts). `match` is True only when both are
known and name the same commit; None when either is unknown.
"""
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

APPROVED_GLOBS = (
    "backend/routes/realtime*.py",
    "backend/routes/aria_*.py",
    "backend/routes/session_grounding.py",
    "backend/routes/resident_session_binding.py",
    "backend/routes/kiosk_identity.py",
    "backend/routes/room_call_request.py",
    "backend/routes/self_code_*.py",
    "backend/routes/memory.py",
    "backend/routes/research.py",
    "backend/routes/research_guard.py",
    "backend/routes/research_openai_search.py",
    "backend/routes/devices.py",
    "backend/routes/tv_remote_setup.py",
    "backend/device_adapters.py",
    "backend/device_ir_adapter.py",
    "backend/ir_codesets.py",
    "backend/aria_guidance_profiles.py",
    "room-node/aria_wake/*.py",
    "room-node/aria_wake/README.md",
    "room-node/aria_wake/serve_built.js",
    "frontend/src/lib/realtime*.js",
    "frontend/src/lib/useRealtimeVoice.js",
    "frontend/src/lib/useWakeWord.js",
    "frontend/src/lib/wakeWordClient.js",
    "frontend/src/lib/callAudioDuck.js",
    "frontend/src/lib/endController.js",
    "frontend/src/lib/endingPhrases.js",
    "frontend/src/lib/powerDirection.js",
    "frontend/src/lib/claim*.js",
    "frontend/src/lib/researchShape.js",
    "frontend/src/pages/Kiosk.jsx",
    "docs/CAOSCARE_PRODUCT_BASELINE.md",
    "docs/ARIA_LANE_ONBOARDING.md",
    "docs/ARIA_CONVERSATION_SUBSTRATE.md",
    "docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md",
    "docs/ROOM_AUDIO_ARCHITECTURE.md",
    "docs/ARIA_WAKE_WORD_ARCHITECTURE.md",
    "docs/ROOM214_SELF_CODE_INSPECTION.md",
    "AGENTS.md",
)
ALLOWED_SUFFIXES = {".py", ".js", ".jsx", ".md", ".txt"}
DENY_NAME = re.compile(r"(^|[/._-])(env|secret|secrets|credential|credentials|password|passwd|token|tokens|"
                       r"key|keys|id_rsa|id_ed25519|pem|cookie|cookies)([/._-]|$)", re.IGNORECASE)
SIZE_CAP = 512 * 1024
MAX_LINES = 120
MAX_CHARS = 12_000
MAX_QUERY = 80
MAX_RESULTS = 25
PER_FILE_RESULTS = 5
_SECRET_LINE = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|mongodb(\+srv)?://\S+|AKIA[0-9A-Z]{12,}|"
                          r"Bearer\s+[A-Za-z0-9._-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")


class SourceRefused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _looks_binary(path: Path) -> bool:
    with path.open("rb") as f:
        return b"\0" in f.read(8192)


def _eligible(rel: str) -> bool:
    if DENY_NAME.search(rel):
        return False
    p = REPO_ROOT / rel
    if p.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    try:
        if p.is_symlink() or not p.is_file():
            return False
        # Every component must be the real checkout path (no symlink escape).
        if p.resolve(strict=True) != p:
            return False
        if p.stat().st_size > SIZE_CAP or _looks_binary(p):
            return False
    except OSError:
        return False
    return True


def approved_files() -> list[str]:
    """Sorted repo-relative paths currently readable. Computed from the
    checkout on each call so a file that appears or disappears is reflected."""
    found: set = set()
    for pattern in APPROVED_GLOBS:
        for p in REPO_ROOT.glob(pattern):
            rel = p.relative_to(REPO_ROOT).as_posix()
            if _eligible(rel):
                found.add(rel)
    return sorted(found)


def resolve(rel: Optional[str]) -> str:
    """Validate a caller-supplied repo-relative path; return it normalized.
    Raises SourceRefused with a reason code for anything not allowed."""
    if not rel or not isinstance(rel, str) or len(rel) > 300:
        raise SourceRefused("path_required")
    if "\0" in rel or "\\" in rel or rel.startswith(("/", "~")) or ":" in rel:
        raise SourceRefused("path_not_relative")
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise SourceRefused("path_traversal")
    if rel not in approved_files():
        raise SourceRefused("path_not_approved")
    return rel


def redact(line: str) -> str:
    return _SECRET_LINE.sub("[redacted]", line)


def read_lines(rel: str, start: int, end: Optional[int]) -> dict:
    """Lines start..end (1-indexed, inclusive) of an approved file, at most
    MAX_LINES / MAX_CHARS. The caller gets the clamped range back so it can
    say exactly what it read."""
    path = REPO_ROOT / resolve(rel)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        all_lines = f.read().splitlines()
    total = len(all_lines)
    start = max(1, int(start or 1))
    end = int(end) if end else start + MAX_LINES - 1
    end = min(end, start + MAX_LINES - 1, total)
    out, chars = [], 0
    for n in range(start, end + 1):
        text = redact(all_lines[n - 1])
        chars += len(text) + 1
        if chars > MAX_CHARS:
            end = n - 1
            break
        out.append(f"{n}: {text}")
    return {"path": rel, "start": start, "end": end, "total_lines": total, "lines": out,
            "truncated": end < total}


def search(query: Optional[str]) -> dict:
    """Case-insensitive literal search over the approved files."""
    q = (query or "").strip()
    if len(q) < 2 or len(q) > MAX_QUERY:
        raise SourceRefused("query_length")
    needle = q.lower()
    matches, truncated = [], False
    for rel in approved_files():
        per_file = 0
        with (REPO_ROOT / rel).open("r", encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f, 1):
                if needle in line.lower():
                    matches.append({"path": rel, "line": n, "text": redact(line.strip())[:160]})
                    per_file += 1
                    if per_file >= PER_FILE_RESULTS:
                        break
                if len(matches) >= MAX_RESULTS:
                    break
        if len(matches) >= MAX_RESULTS:
            truncated = True
            break
    return {"query": q, "matches": matches, "truncated": truncated}


def _git(*args: str) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def loaded_sha() -> Optional[str]:
    return (os.environ.get("CAOSCARE_RUNTIME_SHA") or "").strip() or None


def _same_commit(a: Optional[str], b: Optional[str]) -> Optional[bool]:
    if not a or not b:
        return None
    a, b = a.lower(), b.lower()
    return a.startswith(b) or b.startswith(a)


def revision(rel: Optional[str] = None) -> dict:
    """Inspected checkout revision vs the backend that is actually serving.
    With `rel`, also whether that file carries uncommitted local changes
    (then the file on disk is not exactly the commit named)."""
    inspected = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    loaded = loaded_sha()
    out = {
        "inspected_sha": inspected, "inspected_branch": branch,
        "loaded_backend_sha": loaded, "backend_match": _same_commit(inspected, loaded),
        "source_root": str(REPO_ROOT),
    }
    if rel:
        status = _git("status", "--porcelain", "--untracked-files=no", "--", rel)
        out["local_modifications"] = None if status is None else bool(status)
    return out
