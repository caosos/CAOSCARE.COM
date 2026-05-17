"""One-time CAOS Care owner bootstrap script.

Run manually from a trusted backend environment after setting:

    CAOSCARE_BOOTSTRAP_OWNER_EMAIL
    CAOSCARE_BOOTSTRAP_OWNER_NAME
    CAOSCARE_BOOTSTRAP_OWNER_PASSWORD

The script refuses to create a user when any owner already exists. It does not
run from application startup, does not enable demo seed, and never prints the
password.
"""
import asyncio
import os
import sys
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models import User  # noqa: E402

REQUIRED_ENV = (
    "MONGO_URL",
    "DB_NAME",
    "JWT_SECRET",
    "CAOSCARE_BOOTSTRAP_OWNER_EMAIL",
    "CAOSCARE_BOOTSTRAP_OWNER_NAME",
    "CAOSCARE_BOOTSTRAP_OWNER_PASSWORD",
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _load_env() -> None:
    load_dotenv(BACKEND_DIR / ".env")


def _owner_doc(email: str, name: str, password: str) -> dict:
    user = User(
        email=email.lower(),
        name=name,
        role="owner",
        auth_provider="jwt",
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
    )
    doc = user.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


async def bootstrap_owner() -> int:
    _load_env()
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))

    mongo_url = _env("MONGO_URL")
    db_name = _env("DB_NAME")
    _env("JWT_SECRET")
    email = _env("CAOSCARE_BOOTSTRAP_OWNER_EMAIL").lower()
    name = _env("CAOSCARE_BOOTSTRAP_OWNER_NAME")
    password = _env("CAOSCARE_BOOTSTRAP_OWNER_PASSWORD")

    client = AsyncIOMotorClient(mongo_url)
    try:
        database = client[db_name]
        existing_owner_count = await database.users.count_documents({"role": "owner"})
        if existing_owner_count:
            raise RuntimeError("Owner bootstrap refused: an owner account already exists.")

        existing_email = await database.users.find_one({"email": email}, {"_id": 0, "email": 1})
        if existing_email:
            raise RuntimeError("Owner bootstrap refused: email is already registered.")

        doc = _owner_doc(email=email, name=name, password=password)
        await database.users.insert_one(doc)
    finally:
        client.close()

    print(f"Created owner account for {email}. Store credentials securely and unset bootstrap env vars.")
    return 0


def main() -> int:
    try:
        return asyncio.run(bootstrap_owner())
    except Exception as exc:
        print(f"Owner bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
