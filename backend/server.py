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
from routes import auth_password as auth_password_routes  # noqa: E402
from routes import residents as resident_routes  # noqa: E402
from routes import resident_analytics as resident_analytics_routes  # noqa: E402
from routes import staff as staff_routes  # noqa: E402
from routes import kiosks as kiosk_routes  # noqa: E402
from routes import demo_kiosk as demo_kiosk_routes  # noqa: E402
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
from routes import task_templates as task_templates_routes  # noqa: E402
from routes import task_detail as task_detail_routes  # noqa: E402
from routes import task_assignment as task_assignment_routes  # noqa: E402
from routes import resident_requests as resident_request_routes  # noqa: E402
from routes import schedule as schedule_routes  # noqa: E402
from routes import menu as menu_routes  # noqa: E402
from routes import menu_ingest as menu_ingest_routes  # noqa: E402
from routes import schedule_ingest as schedule_ingest_routes  # noqa: E402
from routes import email_inbound as email_inbound_routes  # noqa: E402
from routes import call_lifecycle as call_lifecycle_routes  # noqa: E402
from routes import telephony_endpoints as telephony_endpoint_routes  # noqa: E402
from routes import telephony_local as telephony_local_routes  # noqa: E402
from routes import phone_aria as phone_aria_routes  # noqa: E402
from routes import email_inbound_allowlist as email_inbound_allowlist_routes  # noqa: E402
from routes import transportation as transportation_routes  # noqa: E402
from routes import transportation_report as transportation_report_routes  # noqa: E402
from routes import transportation_resources as transportation_resources_routes  # noqa: E402
from routes import transportation_calendar as transportation_calendar_routes  # noqa: E402
from routes import transportation_legacy_slots as transportation_legacy_slots_routes  # noqa: E402
from routes import transportation_voice_context as transportation_voice_context_routes  # noqa: E402
from routes import transportation_assign as transportation_assign_routes  # noqa: E402
from routes import transportation_runs as transportation_runs_routes  # noqa: E402
from routes import transportation_staff as transportation_staff_routes  # noqa: E402
from routes import front_desk as front_desk_routes  # noqa: E402
from routes import departments as department_routes  # noqa: E402
from routes import haiku as haiku_routes  # noqa: E402
from routes import paging as paging_routes  # noqa: E402
from routes import medications as medication_routes  # noqa: E402
from routes import memory as memory_routes  # noqa: E402
from routes import realtime_memory_ingest as realtime_memory_ingest_routes  # noqa: E402
from routes import audit as audit_routes  # noqa: E402
from routes import realtime as realtime_routes  # noqa: E402
from routes import realtime_room_lease as realtime_room_lease_routes  # noqa: E402
from routes import rf as rf_routes  # noqa: E402
from routes import rf_bridge_health as rf_bridge_health_routes  # noqa: E402
from routes import rf_fleet as rf_fleet_routes  # noqa: E402
from routes import facilities as facilities_routes  # noqa: E402
from routes import hardware as hardware_routes  # noqa: E402
from routes import escalation as escalation_routes  # noqa: E402
from routes import research as research_routes  # noqa: E402
from routes import weather as weather_routes  # noqa: E402
from routes import timers as timer_routes  # noqa: E402
from routes import capabilities as capability_routes  # noqa: E402
from routes import aria_memory as aria_memory_routes  # noqa: E402
from routes import receipts as receipt_routes  # noqa: E402
from routes import realtime_diagnostics as realtime_diagnostics_routes  # noqa: E402
from routes import resident_conversations as resident_conversations_routes  # noqa: E402
from routes import admin_assistant as admin_assistant_routes  # noqa: E402
from routes import events as event_routes  # noqa: E402
from routes import alert_lifecycle_events as alert_lifecycle_routes  # noqa: E402
from routes import resident_patterns as resident_patterns_routes  # noqa: E402
from routes import resident_assistance_config as resident_assistance_config_routes  # noqa: E402
from routes import ops_overview as ops_overview_routes  # noqa: E402
from routes import reports as reports_routes  # noqa: E402
from routes import activation_client_events as activation_client_events_routes  # noqa: E402
from routes import activation_timeline as activation_timeline_routes  # noqa: E402
from routes import staff_dispatch as staff_dispatch_routes  # noqa: E402
from routes import ai_escalation as ai_escalation_routes  # noqa: E402
from routes import aria_operational_state as aria_operational_state_routes  # noqa: E402
from routes import aria_continuity as aria_continuity_routes  # noqa: E402
from routes import aria_conversation_state as aria_conversation_state_routes  # noqa: E402
from routes import aria_interpretation_patterns as aria_interpretation_patterns_routes  # noqa: E402
from routes import aria_turn_taking as aria_turn_taking_routes  # noqa: E402
from routes import simulation as simulation_routes  # noqa: E402
from routes import demo_continuity as demo_continuity_routes  # noqa: E402
from seed import demo_seed_enabled, seed  # noqa: E402


def _cors_origins() -> list[str]:
    """Return explicit CORS origins for credentialed browser requests.

    Credentialed requests cannot use Access-Control-Allow-Origin: *.
    The deployed CAOS Care frontend uses withCredentials=True, so the backend
    must return the exact requesting origin.
    """
    configured = os.environ.get("CORS_ORIGINS", "")
    defaults = "https://caoscare.com,https://www.caoscare.com,http://localhost:3000,http://127.0.0.1:3000"
    raw = configured or defaults
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if demo_seed_enabled():
        try:
            await seed()
        except Exception as e:
            logging.warning(f"Seed failed: {e}")
    else:
        logging.warning(
            "Demo seed skipped; set CAOSCARE_ENABLE_DEMO_SEED=true only for local/demo environments."
        )
    # Always seeds (unlike demo data above) - the department list is real
    # operational config, not demo content, and other routes assume at
    # least the baseline departments exist. No-ops if any already do.
    from routes.departments import seed_default_departments
    await seed_default_departments()
    # Substrate lookup indexes — built once here, never in the session-mint
    # / context-assembly path.
    from routes.aria_continuity import ensure_indexes as _ensure_continuity_indexes
    try:
        await _ensure_continuity_indexes()
    except Exception as e:
        logging.warning(f"continuity index setup skipped: {e}")
    # RQ-001: demo room catch-up. Background only; does nothing unless
    # CAOSCARE_DEMO_CONTINUITY_AUTO is set.
    from demo_continuity import catch_up_in_background
    catch_up_in_background("startup")
    # Phone call-state truth: Asterisk ARI events. No-op unless
    # ASTERISK_ARI_URL/USER/PASSWORD are configured.
    import asyncio
    from routes.asterisk_ari_events import run_ari_listener, ari_ws_url
    ari_task = asyncio.create_task(run_ari_listener()) if ari_ws_url() else None
    # Escalation schedule (independent of any simulator); CAOSCARE_ESCALATION_AUTO=0 disables.
    from routes.escalation_tick import auto_interval_seconds, run_escalation_loop
    esc_interval = auto_interval_seconds()
    esc_task = asyncio.create_task(run_escalation_loop(esc_interval)) if esc_interval else None
    yield
    if ari_task:
        ari_task.cancel()
    if esc_task:
        esc_task.cancel()


app = FastAPI(title="CAOS Care", lifespan=lifespan)

api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"service": "CAOS Care", "status": "ok"}


@api.get("/health")
async def health():
    try:
        await db.command("ping")
        body = {"ok": True, "db": "up"}
    except Exception as e:
        body = {"ok": False, "db": str(e)}
    # Backend test gate only: echo the gate run's nonce so the gate can prove
    # the server answering on its port is the one it started.
    if os.environ.get("CAOSCARE_TEST_HOOKS") and os.environ.get("CAOSCARE_TEST_GATE_RUN_ID"):
        body["gate_run_id"] = os.environ["CAOSCARE_TEST_GATE_RUN_ID"]
    return body


api.include_router(auth_routes.router)
api.include_router(auth_password_routes.router)
api.include_router(resident_routes.router)
api.include_router(resident_analytics_routes.router)
api.include_router(staff_routes.router)
api.include_router(kiosk_routes.router)
api.include_router(demo_kiosk_routes.router)
api.include_router(alert_routes.router)
api.include_router(location_routes.router)
api.include_router(ai_routes.router)
api.include_router(pendant_routes.router)
api.include_router(roadmap_routes.router)
api.include_router(insight_routes.router)
api.include_router(notification_routes.router)
api.include_router(call_lifecycle_routes.router)
api.include_router(telephony_endpoint_routes.router)
api.include_router(telephony_local_routes.router)
api.include_router(phone_aria_routes.router)
api.include_router(wearable_routes.router)
api.include_router(device_auth_routes.router)
api.include_router(family_portal_routes.router)
api.include_router(device_routes.router)
api.include_router(vision_routes.router)
api.include_router(task_routes.router)
api.include_router(task_templates_routes.router)
api.include_router(task_detail_routes.router)
api.include_router(task_assignment_routes.router)
api.include_router(resident_request_routes.router)
api.include_router(schedule_routes.router)
api.include_router(menu_routes.router)
api.include_router(menu_ingest_routes.router)
api.include_router(schedule_ingest_routes.router)
api.include_router(email_inbound_routes.router)
api.include_router(email_inbound_allowlist_routes.router)
api.include_router(transportation_routes.router)
api.include_router(transportation_report_routes.router)
api.include_router(transportation_resources_routes.router)
api.include_router(transportation_calendar_routes.router)
api.include_router(transportation_legacy_slots_routes.router)
api.include_router(transportation_voice_context_routes.router)
api.include_router(transportation_assign_routes.router)
api.include_router(transportation_runs_routes.router)
api.include_router(transportation_staff_routes.router)
api.include_router(front_desk_routes.router)
api.include_router(department_routes.router)
api.include_router(haiku_routes.router)
api.include_router(paging_routes.router)
api.include_router(medication_routes.router)
api.include_router(memory_routes.router)
api.include_router(realtime_memory_ingest_routes.router)
api.include_router(audit_routes.router)
api.include_router(realtime_routes.router)
api.include_router(realtime_room_lease_routes.router)
api.include_router(rf_routes.router)
api.include_router(rf_bridge_health_routes.router)
api.include_router(rf_fleet_routes.router)
api.include_router(facilities_routes.router)
api.include_router(hardware_routes.router)
api.include_router(escalation_routes.router)
api.include_router(research_routes.router)
api.include_router(weather_routes.router)
api.include_router(timer_routes.router)
api.include_router(capability_routes.router)
api.include_router(aria_memory_routes.router)
api.include_router(receipt_routes.router)
api.include_router(realtime_diagnostics_routes.router)
api.include_router(resident_conversations_routes.router)
api.include_router(admin_assistant_routes.router)
api.include_router(event_routes.router)
api.include_router(alert_lifecycle_routes.router)
api.include_router(resident_patterns_routes.router)
api.include_router(resident_assistance_config_routes.router)
api.include_router(ops_overview_routes.router)
api.include_router(reports_routes.router)
api.include_router(activation_client_events_routes.router)
api.include_router(activation_timeline_routes.router)
api.include_router(staff_dispatch_routes.router)
api.include_router(ai_escalation_routes.router)
api.include_router(aria_operational_state_routes.router)
api.include_router(aria_continuity_routes.router)
api.include_router(aria_conversation_state_routes.router)
api.include_router(aria_interpretation_patterns_routes.router)
api.include_router(aria_turn_taking_routes.router)
api.include_router(simulation_routes.router)
api.include_router(demo_continuity_routes.router)

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
