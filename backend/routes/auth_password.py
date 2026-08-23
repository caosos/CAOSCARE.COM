"""Self-service password change - split out of auth.py to keep that file
under the repo's 300-line cap. Same /auth prefix, registered as its own
router alongside auth.py's.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.auth import _hash_pw, _verify_pw

router = APIRouter(prefix="/auth", tags=["auth"])


class ChangePasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/change-password")
async def change_password(data: ChangePasswordInput, request: Request):
    """Self-service - any authenticated user changes their own password.
    Requires the current one, unlike the admin override at
    POST /staff/{user_id}/password. get_current_user() deliberately never
    returns password_hash (every other caller of it shouldn't see it) -
    re-fetch the full doc here, the one place that legitimately needs it,
    rather than loosening what the shared dependency exposes everywhere.
    If the account has no password yet (Google-only sign-in), there's
    nothing to verify against - point them at an admin to set one."""
    current_user = await get_current_user(request)
    full_user = await db.users.find_one({"user_id": current_user["user_id"]}, {"_id": 0})
    if not full_user.get("password_hash"):
        raise HTTPException(
            status_code=400,
            detail="This account has no password set (Google sign-in only) - ask an admin to set one for you.",
        )
    if not _verify_pw(data.current_password, full_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    await db.users.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"password_hash": _hash_pw(data.new_password)}},
    )
    return {"ok": True}
