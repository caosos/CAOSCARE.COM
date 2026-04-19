"""CAOS Care - main FastAPI entry."""
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from deps import db  # noqa: E402
from routes import auth as auth_routes  # noqa: E402
from routes import residents as resident_routes  # noqa: E402
from routes import staff as staff_routes  # noqa: E402
from routes import kiosks as kiosk_routes  # noqa: E402
from routes import alerts as alert_routes  # noqa: E402
from routes import location as location_routes  # noqa: E402
from routes import ai as ai_routes  # noqa: E402
from seed import seed  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await seed()
    except Exception as e:
        logging.warning(f"Seed failed: {e}")
    yield


app = FastAPI(title="CAOS Care", lifespan=lifespan)

api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"service": "CAOS Care", "status": "ok"}


@api.get("/health")
async def health():
    try:
        await db.command("ping")
        return {"ok": True, "db": "up"}
    except Exception as e:
        return {"ok": False, "db": str(e)}


api.include_router(auth_routes.router)
api.include_router(resident_routes.router)
api.include_router(staff_routes.router)
api.include_router(kiosk_routes.router)
api.include_router(alert_routes.router)
api.include_router(location_routes.router)
api.include_router(ai_routes.router)

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
