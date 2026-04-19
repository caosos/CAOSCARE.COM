"""Staff users CRUD (admin only)."""
from fastapi import APIRouter, HTTPException, Depends
from models import RegisterInput, User, UserPublic
from deps import db, require_admin
import bcrypt


router = APIRouter(prefix="/staff", tags=["staff"])


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


@router.get("")
async def list_staff(user=Depends(require_admin)):
    items = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("name", 1).to_list(1000)
    return items


@router.post("")
async def create_staff(data: RegisterInput, user=Depends(require_admin)):
    existing = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    staff = User(
        email=data.email.lower(),
        name=data.name,
        role=data.role,
        auth_provider="jwt",
        password_hash=_hash_pw(data.password),
    )
    doc = staff.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.users.insert_one(doc)
    return UserPublic(**staff.model_dump()).model_dump()


@router.delete("/{user_id}")
async def delete_staff(user_id: str, user=Depends(require_admin)):
    if user.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    r = await db.users.delete_one({"user_id": user_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Staff not found")
    return {"ok": True}
