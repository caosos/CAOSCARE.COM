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
from routes import pendants as pendant_routes  # noqa: E402
from routes import roadmap as roadmap_routes  # noqa: E402
from routes import insights as insight_routes  # noqa: E402
from routes import notifications as notification_routes  # noqa: E402
from routes import wearables as wearable_routes  # noqa: E402
from routes import device_auth as device_auth_routes  # noqa: E402
from routes import family_portal as family_portal_routes  # noqa: E402
from routes import devices as device_routes  # noqa: E402
from routes import vision as vision_routes  # noqa: E402
from routes import tasks as task_routes  # noqa: E402
from routes import haiku as haiku_routes  # noqa: E402
from routes import paging as paging_routes  # noqa: E402
from routes import medications as medication_routes  # noqa: E402
from routes import memory as memory_routes  # noqa: E402
from routes import audit as audit_routes  # noqa: E402
from routes import realtime as realtime_routes  # noqa: E402
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
api.include_router(pendant_routes.router)
api.include_router(roadmap_routes.router)
api.include_router(insight_routes.router)
api.include_router(notification_routes.router)
api.include_router(wearable_routes.router)
api.include_router(device_auth_routes.router)
api.include_router(family_portal_routes.router)
api.include_router(device_routes.router)
api.include_router(vision_routes.router)
api.include_router(task_routes.router)
api.include_router(haiku_routes.router)
api.include_router(paging_routes.router)
api.include_router(medication_routes.router)
api.include_router(memory_routes.router)
api.include_router(audit_routes.router)
api.include_router(realtime_routes.router)

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
