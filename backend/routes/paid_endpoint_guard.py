"""Abuse limits for public endpoints that spend OpenAI money (TTS, vision).

Found by the 2026-10-10 route audit: /ai/chat, /ai/stt, /ai/tts and /vision/* had no auth and no limit, so anyone
who could reach the backend could run up the OpenAI bill. /ai/chat and /ai/stt have no caller and are now admin-only
(see routes/ai.py); the kiosk and the glasses still need TTS/vision without a login, so those get a per-client rate
limit. In memory, per process, per client IP (X-Forwarded-For first hop when behind the proxy).
"""
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

WINDOW_SECONDS = 60.0
_hits: dict = defaultdict(deque)


def _per_min(env: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(env, default)))
    except ValueError:
        return default


def client_key(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "unknown")


def reset() -> None:
    _hits.clear()


def limit(bucket: str, env: str, default: int):
    """FastAPI dependency factory: at most `env` (default `default`) calls per minute per client for this bucket."""
    async def dep(request: Request):
        now = time.monotonic()
        q = _hits[f"{bucket}:{client_key(request)}"]
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= _per_min(env, default):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
        q.append(now)
    return dep
