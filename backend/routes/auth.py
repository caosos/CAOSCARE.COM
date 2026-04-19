"""Auth routes - JWT login/register + Emergent Google session exchange."""
import os
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
        role=data.role,
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
        # First registered user becomes admin
        count = await db.users.count_documents({})
        role = "admin" if count == 0 else "staff"
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
