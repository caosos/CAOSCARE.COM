"""Shared dependencies: Mongo connection + current user auth."""
import os
from datetime import datetime, timezone
from fastapi import Request, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
_client = AsyncIOMotorClient(mongo_url)
db = _client[os.environ["DB_NAME"]]


async def get_current_user(request: Request):
    """Accepts either JWT Bearer token OR Emergent session_token cookie/header."""
    import jwt

    token = None
    source = None

    # 1. Authorization header
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        source = "bearer"

    # 2. session_token cookie
    cookie_token = request.cookies.get("session_token")
    if cookie_token and not token:
        token = cookie_token
        source = "cookie"

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Try JWT first
    jwt_secret = os.environ["JWT_SECRET"]
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if user_id:
            user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
            if user:
                return user
    except jwt.PyJWTError:
        pass

    # Fallback: treat as session_token (Emergent Google Auth)
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if session:
        expires_at = session["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})
        if user:
            return user

    raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_admin(request: Request):
    """Admin-tier access: owner or admin (clinical). Staff are rejected."""
    user = await get_current_user(request)
    if user.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_owner(request: Request):
    """System-owner-only access. Used for Blueprint, memory bulletin internals,
    and any route that exposes architecture or all-resident override."""
    user = await get_current_user(request)
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="System owner access required")
    return user
