"""Auth routes - JWT login/register + Emergent Google session exchange."""
import os
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel
import jwt
import bcrypt
import httpx

from models import RegisterInput, LoginInput, User, UserPublic, uid, now_utc
from deps import db, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
JWT_EXPIRE_DAYS = 7

# Dummy bcrypt hash used to equalize timing when the email is unknown, so
# /admin-login doesn't leak which admin emails exist via response latency.
_DUMMY_HASH = bcrypt.hashpw(b"dummy_placeholder_never_matches", bcrypt.gensalt()).decode()

# Simple in-memory admin-login throttle: { "ip:email": [ts, ts, ...] }. Any
# identifier with 5+ failed attempts in the last 15 min is locked out.
_ADMIN_ATTEMPTS: dict[str, list[float]] = {}
ADMIN_LOCKOUT_MAX = 5
ADMIN_LOCKOUT_WINDOW_S = 15 * 60


def _admin_throttle_check(ip: str, email: str) -> None:
    key = f"{ip}:{email.lower()}"
    now = time.time()
    attempts = [t for t in _ADMIN_ATTEMPTS.get(key, []) if now - t < ADMIN_LOCKOUT_WINDOW_S]
    _ADMIN_ATTEMPTS[key] = attempts
    if len(attempts) >= ADMIN_LOCKOUT_MAX:
        raise HTTPException(status_code=429, detail="Too many admin sign-in attempts. Try again in 15 minutes.")


def _admin_throttle_record(ip: str, email: str) -> None:
    key = f"{ip}:{email.lower()}"
    _ADMIN_ATTEMPTS.setdefault(key, []).append(time.time())


def _admin_throttle_clear(ip: str, email: str) -> None:
    _ADMIN_ATTEMPTS.pop(f"{ip}:{email.lower()}", None)


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def _issue_jwt(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


@router.post("/register")
async def register(data: RegisterInput):
    existing = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=data.email.lower(),
        name=data.name,
        # Public self-registration is staff-only. Owner/admin accounts must be
        # created through a controlled bootstrap or admin-managed flow.
        role="staff",
        auth_provider="jwt",
        password_hash=_hash_pw(data.password),
    )
    doc = user.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.users.insert_one(doc)
    token = _issue_jwt(user.user_id)
    return {
        "token": token,
        "user": UserPublic(**user.model_dump()).model_dump(),
    }


@router.post("/login")
async def login(data: LoginInput):
    user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not _verify_pw(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _issue_jwt(user["user_id"])
    return {
        "token": token,
        "user": UserPublic(**user).model_dump(),
    }


@router.post("/admin-login")
async def admin_login(data: LoginInput, request: Request):
    """Admin-only sign-in. Separate endpoint so the admin console has its own
    branded path and staff credentials can't slip in through the front door.

    - Rate-limited per (ip, email) to slow brute-force attempts on admin accounts.
    - Constant-time response when email is unknown — no user enumeration.
    - Rejects non-admin accounts with a 403 and a message pointing them to /login.
    """
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    _admin_throttle_check(client_ip, data.email)

    user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})

    # Always run bcrypt once so missing-user responses are timing-equivalent.
    pw_ok = _verify_pw(data.password, user["password_hash"] if user and user.get("password_hash") else _DUMMY_HASH)

    if not user or not user.get("password_hash") or not pw_ok:
        _admin_throttle_record(client_ip, data.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.get("role") not in ("owner", "admin"):
        # Do NOT increment the lockout counter for a valid staff login — that
        # would let a malicious admin lock out legit staff. Just redirect.
        raise HTTPException(
            status_code=403,
            detail="These are staff credentials. Please sign in at the staff portal.",
        )

    _admin_throttle_clear(client_ip, data.email)
    token = _issue_jwt(user["user_id"])
    return {
        "token": token,
        "user": UserPublic(**user).model_dump(),
    }


@router.get("/me")
async def me(request: Request):
    user = await get_current_user(request)
    return UserPublic(**user).model_dump()


class GoogleSessionInput(BaseModel):
    session_id: str


@router.post("/google/session")
async def google_session(data: GoogleSessionInput, response: Response):
    """Exchange Emergent Google Auth session_id for a server session."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": data.session_id},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google session")
        gdata = r.json()

    email = gdata["email"].lower()
    name = gdata.get("name") or email.split("@")[0]
    picture = gdata.get("picture")
    session_token = gdata["session_token"]

    # Upsert user
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "auth_provider": "google"}},
        )
        role = existing.get("role", "staff")
    else:
        user_id = uid("user")
        # First registered user becomes owner (system-owner), subsequent = staff
        count = await db.users.count_documents({})
        role = "owner" if count == 0 else "staff"
        doc = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": role,
            "auth_provider": "google",
            "created_at": now_utc().isoformat(),
        }
        await db.users.insert_one(doc)

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user_id,
        "expires_at": expires_at,
        "created_at": now_utc(),
    })

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return {
        "user": {
            "user_id": user_id,
            "email": email,
            "name": name,
            "role": role,
            "picture": picture,
            "auth_provider": "google",
        }
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}
