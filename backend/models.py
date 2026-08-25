from datetime import datetime, timezone
from typing import List, Optional, Literal
from zoneinfo import ZoneInfo, available_timezones
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
import uuid


def uid(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# 2026-08-25: a real facility record was found with "conway ar 72034" saved
# in its timezone field (city/state/zip text, not a zone) - the model had no
# dedicated place for that text to go and no validation to catch it landing
# in the wrong field. Shared by Facility/FacilityCreate/FacilityUpdate below.
def _validate_timezone(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in available_timezones():
        raise ValueError(f"{v!r} is not a valid IANA timezone (e.g. 'America/Chicago')")
    ZoneInfo(v)  # confirms it actually loads, not just listed
    return v


# ---------- Facility (multi-tenant root) ----------
class Facility(BaseModel):
    """A senior-living facility. Top-level tenant. Every other entity should
    eventually carry facility_id; for now we add it as Optional so existing
    single-tenant data keeps working while new flows are scoped.

    city/state/country/lat/lon added 2026-08-25 - previously only a single
    free-text `address` existed, with nowhere structured for the Realtime
    voice system (or weather's coordinate lookup) to read facility location
    from, which is why a resident could not be told what city they were in."""
    model_config = ConfigDict(extra="ignore")
    facility_id: str = Field(default_factory=lambda: uid("fac"))
    name: str
    timezone: str = "America/New_York"
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "US"
    lat: Optional[float] = None
    lon: Optional[float] = None
    phone: Optional[str] = None
    contact_email: Optional[str] = None
    on_call_phone: Optional[str] = None    # default escalation number
    plan: Literal["pilot", "standard", "enterprise"] = "pilot"
    is_active: bool = True
    created_at: datetime = Field(default_factory=now_utc)

    _check_tz = field_validator("timezone")(_validate_timezone)


class FacilityCreate(BaseModel):
    name: str
    timezone: str = "America/New_York"
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "US"
    lat: Optional[float] = None
    lon: Optional[float] = None
    phone: Optional[str] = None
    contact_email: Optional[str] = None
    on_call_phone: Optional[str] = None
    plan: Literal["pilot", "standard", "enterprise"] = "pilot"

    _check_tz = field_validator("timezone")(_validate_timezone)


class FacilityUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    phone: Optional[str] = None
    contact_email: Optional[str] = None
    on_call_phone: Optional[str] = None
    plan: Optional[Literal["pilot", "standard", "enterprise"]] = None
    is_active: Optional[bool] = None

    _check_tz = field_validator("timezone")(_validate_timezone)


# ---------- Users (staff / admin) ----------
# Department is optional and separate from role (owner/admin/staff): role
# is the auth tier, department is which request queues a "staff" user sees
# (Terminal 8 item 4 - role-based visibility). None = general staff, sees
# only "all_staff"-visibility requests, not department-specific ones.
#
# Departments themselves are admin-managed data (see Department below), not
# a fixed code list - was a Literal enum through "transportation" (item 5),
# changed to a plain str once Michael asked for "every other dept" to be
# addable without a code change. A department slug (User.department,
# StaffTask.visibility_role) is just a string that happens to match a real
# Department.slug; nothing at the type level enforces that anymore -
# routes/departments.py and the resident-request category check are where
# that's actually validated.
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str = Field(default_factory=lambda: uid("user"))
    email: str
    name: str
    role: Literal["owner", "admin", "staff", "front_desk"] = "staff"
    department: Optional[str] = None
    picture: Optional[str] = None
    auth_provider: Literal["jwt", "google"] = "jwt"
    password_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)


class UserPublic(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    department: Optional[str] = None
    picture: Optional[str] = None
    auth_provider: str


class RegisterInput(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: Literal["owner", "admin", "staff", "front_desk"] = "staff"


class LoginInput(BaseModel):
    email: EmailStr
    password: str


# ---------- Residents ----------
ParticipationLevel = Literal["room_only", "pendant_enhanced", "wearable_enhanced", "family_connected", "full"]


class ClinicalThresholds(BaseModel):
    """Per-resident vitals bands. Any field left None → fall back to generic
    wearable-reported event typing. These are not diagnostic — they simply
    let CAOS stop spamming "heart rate high" alerts on a resident whose
    resting HR happens to run above a generic default."""
    model_config = ConfigDict(extra="ignore")
    hr_resting_min: Optional[int] = Field(default=None, ge=0, le=300)
    hr_resting_max: Optional[int] = Field(default=None, ge=0, le=300)
    hr_exertion_max: Optional[int] = Field(default=None, ge=0, le=300)
    spo2_min: Optional[int] = Field(default=None, ge=0, le=100)
    inactivity_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    notes: Optional[str] = ""                    # clinician note, e.g. "chronic afib, expect 100–120 resting"


class Resident(BaseModel):
    model_config = ConfigDict(extra="ignore")
    resident_id: str = Field(default_factory=lambda: uid("res"))
    name: str
    room: str
    pendant_id: str
    photo: Optional[str] = None
    medical_notes: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    date_of_birth: Optional[str] = None
    participation_level: ParticipationLevel = "pendant_enhanced"
    preferences: Optional[str] = ""   # likes, hobbies, prayers, comfort topics
    memory: Optional[str] = ""         # things the AI should remember about them
    preferred_name: Optional[str] = ""
    clinical_thresholds: Optional[ClinicalThresholds] = None
    created_at: datetime = Field(default_factory=now_utc)


class ResidentCreate(BaseModel):
    name: str
    room: str
    pendant_id: str
    photo: Optional[str] = None
    medical_notes: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    date_of_birth: Optional[str] = None
    participation_level: ParticipationLevel = "pendant_enhanced"
    preferences: Optional[str] = ""
    memory: Optional[str] = ""
    preferred_name: Optional[str] = ""
    clinical_thresholds: Optional[ClinicalThresholds] = None


# ---------- Kiosks / Zones ----------
class Kiosk(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kiosk_id: str = Field(default_factory=lambda: uid("kio"))
    name: str
    room: str
    zone: str
    mac_address: Optional[str] = None
    status: Literal["online", "offline"] = "online"
    is_central: bool = False  # central station listens for ANY resident's emergency, not just its zone
    created_at: datetime = Field(default_factory=now_utc)


class KioskCreate(BaseModel):
    name: str
    room: str
    zone: str
    mac_address: Optional[str] = None
    is_central: bool = False


class Zone(BaseModel):
    model_config = ConfigDict(extra="ignore")
    zone_id: str = Field(default_factory=lambda: uid("zone"))
    name: str
    floor: Optional[str] = None
    description: Optional[str] = ""
    is_restricted: bool = False           # wander / elopement trigger
    is_bathroom: bool = False             # used for bathroom-frequency drift analysis
    allowed_levels: Optional[List[ParticipationLevel]] = None  # if set, only these participation levels may enter
    created_at: datetime = Field(default_factory=now_utc)


class ZoneCreate(BaseModel):
    name: str
    floor: Optional[str] = None
    description: Optional[str] = ""
    is_restricted: bool = False
    is_bathroom: bool = False
    allowed_levels: Optional[List[ParticipationLevel]] = None


# ---------- Alerts ----------
AlertSeverity = Literal["emergency", "assist", "comfort"]
AlertStatus = Literal["active", "acknowledged", "resolved"]
AlertCategory = Literal[
    "bathroom", "fall", "pain", "medication", "confusion",
    "loneliness", "comfort", "mobility", "other",
]


class Alert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    alert_id: str = Field(default_factory=lambda: uid("alert"))
    kiosk_id: Optional[str] = None
    pendant_id: Optional[str] = None
    frequency: Optional[float] = None
    resident_id: Optional[str] = None
    resident_name: Optional[str] = None
    room: Optional[str] = None
    zone: Optional[str] = None
    severity: AlertSeverity = "assist"
    status: AlertStatus = "active"
    escalation_level: int = 0  # 0=normal, 1=escalated, 2=supervisor, 3=code
    message: Optional[str] = ""
    triggered_by: Literal["kiosk_button", "ai_triage", "pendant", "manual", "geofence", "wearable", "rf_pendant"] = "kiosk_button"
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    outcome: Optional[str] = None      # e.g. "assisted to bathroom"
    close_notes: Optional[str] = None
    auto_voice: bool = False             # hands-free mic activation on kiosk (panic-press / fall)
    press_count: int = 1                 # how many rapid presses triggered this
    source_metadata: Optional[dict] = None  # arbitrary trigger-specific payload (rf_device_id, rssi, etc.)
    # ---- Event registry enrichment (auto-populated by AI classifier) ----
    category: Optional[AlertCategory] = None     # what kind of call (bathroom, fall, ...)
    ai_summary: Optional[str] = None             # 1-line Claude summary of the call
    resident_stated_reason: Optional[str] = None # first thing resident actually said
    response_seconds: Optional[int] = None       # time-to-acknowledge
    duration_seconds: Optional[int] = None       # acknowledge → resolved
    conversation_turns: Optional[int] = None     # how long CAOS talked with them
    created_at: datetime = Field(default_factory=now_utc)


class AlertCreate(BaseModel):
    kiosk_id: Optional[str] = None
    pendant_id: Optional[str] = None
    frequency: Optional[float] = None
    resident_id: Optional[str] = None
    severity: AlertSeverity = "assist"
    message: Optional[str] = ""
    triggered_by: Literal["kiosk_button", "ai_triage", "pendant", "manual", "geofence", "wearable"] = "kiosk_button"


class AlertClose(BaseModel):
    outcome: str
    close_notes: Optional[str] = ""
    category: Optional[AlertCategory] = None


# ---------- Location updates ----------
class LocationUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update_id: str = Field(default_factory=lambda: uid("loc"))
    resident_id: str
    zone: str
    room: Optional[str] = None
    signal_strength: Optional[int] = None
    source: Literal["mesh", "pendant", "mock"] = "mesh"
    created_at: datetime = Field(default_factory=now_utc)


class LocationUpdateCreate(BaseModel):
    resident_id: str
    zone: str
    room: Optional[str] = None
    signal_strength: Optional[int] = None
    source: Literal["mesh", "pendant", "mock"] = "mesh"


# ---------- AI Chat ----------
class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str = Field(default_factory=lambda: uid("msg"))
    session_id: str
    kiosk_id: Optional[str] = None
    resident_id: Optional[str] = None
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime = Field(default_factory=now_utc)


class ChatInput(BaseModel):
    session_id: str
    kiosk_id: Optional[str] = None
    resident_id: Optional[str] = None
    message: str


class TTSInput(BaseModel):
    text: str
    voice: Optional[str] = "sage"


# ---------- Sessions ----------
class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_token: str
    user_id: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=now_utc)


# ---------- Pendant devices ----------
class Pendant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pendant_device_id: str = Field(default_factory=lambda: uid("pend"))
    pendant_id: str                        # printed serial / human label
    frequency_mhz: float                   # e.g. 916.125
    resident_id: Optional[str] = None
    battery_percent: Optional[int] = None
    signal_strength: Optional[int] = None
    last_seen_at: Optional[datetime] = None
    status: Literal["active", "inactive", "lost", "low_battery"] = "active"
    notes: Optional[str] = ""
    created_at: datetime = Field(default_factory=now_utc)


class PendantCreate(BaseModel):
    pendant_id: str
    frequency_mhz: float
    resident_id: Optional[str] = None
    battery_percent: Optional[int] = None
    status: Literal["active", "inactive", "lost", "low_battery"] = "active"
    notes: Optional[str] = ""


class PendantEventInput(BaseModel):
    """POST from Android bridge app when pendant signal arrives via USB RF receiver."""
    frequency_mhz: float
    signal_strength: Optional[int] = None
    battery_percent: Optional[int] = None
    event_type: Literal["press", "periodic_ping", "fall"] = "press"
    device_token: Optional[str] = None     # receiver tablet identity (optional for MVP)
    zone: Optional[str] = None             # reported by the receiver tablet's known zone


# ---------- Roadmap / phase checklist ----------
RoadmapStatus = Literal["not_started", "in_progress", "done", "blocked"]


class RoadmapItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_id: str = Field(default_factory=lambda: uid("road"))
    phase: int
    title: str
    description: Optional[str] = ""
    status: RoadmapStatus = "not_started"
    notes: Optional[str] = ""
    order: int = 0
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class RoadmapItemUpdate(BaseModel):
    status: Optional[RoadmapStatus] = None
    notes: Optional[str] = None


# ---------- Insights / pattern detection ----------
InsightSeverity = Literal["info", "watch", "concern"]


class Insight(BaseModel):
    model_config = ConfigDict(extra="ignore")
    insight_id: str = Field(default_factory=lambda: uid("ins"))
    resident_id: str
    resident_name: Optional[str] = None
    metric: str                  # e.g. "help_requests_7d", "nighttime_activity_7d"
    current_value: float
    baseline_value: float
    deviation_pct: float         # 0.3 = 30% above baseline
    severity: InsightSeverity
    confidence: float            # 0-1
    title: str
    description: str
    created_at: datetime = Field(default_factory=now_utc)


# ---------- Notifications ----------
NotificationChannel = Literal["sms", "email", "pager", "inapp"]
NotificationStatus = Literal["queued", "sent", "failed", "logged"]


class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    notification_id: str = Field(default_factory=lambda: uid("notif"))
    channel: NotificationChannel
    to: str                       # phone or email
    subject: Optional[str] = ""
    body: str
    alert_id: Optional[str] = None
    resident_id: Optional[str] = None
    status: NotificationStatus = "logged"
    provider_response: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)


class NotificationTest(BaseModel):
    channel: NotificationChannel
    to: str
    body: str
    subject: Optional[str] = "CAOS Care test"


# ---------- Family contacts ----------
class FamilyContact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact_id: str = Field(default_factory=lambda: uid("fam"))
    resident_id: str
    name: str
    relationship: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    notify_on: List[Literal["emergency", "assist", "wander", "daily_summary"]] = Field(default_factory=lambda: ["emergency", "wander"])
    portal_token: str = Field(default_factory=lambda: uid("ptok"))   # magic-link token for family portal
    created_at: datetime = Field(default_factory=now_utc)


class FamilyContactCreate(BaseModel):
    resident_id: str
    name: str
    relationship: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    notify_on: List[Literal["emergency", "assist", "wander", "daily_summary"]] = Field(default_factory=lambda: ["emergency", "wander"])


# ---------- Wearable devices (P3) ----------
class Wearable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    wearable_id: str = Field(default_factory=lambda: uid("wear"))
    device_label: str                     # human identifier, e.g. "Margaret's blue watch"
    device_type: Literal["smartwatch", "earbuds", "glasses", "ble_beacon", "generic"] = "smartwatch"
    mac_address: Optional[str] = None
    resident_id: Optional[str] = None
    battery_percent: Optional[int] = None
    last_heart_rate: Optional[int] = None
    last_seen_at: Optional[datetime] = None
    status: Literal["active", "inactive", "lost", "low_battery"] = "active"
    notes: Optional[str] = ""
    created_at: datetime = Field(default_factory=now_utc)


class WearableCreate(BaseModel):
    device_label: str
    device_type: Literal["smartwatch", "earbuds", "glasses", "ble_beacon", "generic"] = "smartwatch"
    mac_address: Optional[str] = None
    resident_id: Optional[str] = None
    status: Literal["active", "inactive", "lost", "low_battery"] = "active"
    notes: Optional[str] = ""


class WearableEventInput(BaseModel):
    """Public ingest. Companion phone / watch posts here."""
    wearable_id: Optional[str] = None     # known device id
    mac_address: Optional[str] = None     # or match by MAC
    event_type: Literal["press", "fall", "heart_rate_high", "heart_rate_low", "periodic_ping", "inactivity"] = "press"
    zone: Optional[str] = None
    heart_rate: Optional[int] = None
    battery_percent: Optional[int] = None
    signal_strength: Optional[int] = None
    device_token: Optional[str] = None


# ---------- Device tokens (HMAC auth for field hardware) ----------
class DeviceToken(BaseModel):
    model_config = ConfigDict(extra="ignore")
    token_id: str = Field(default_factory=lambda: uid("devtok"))
    name: str                              # human label, e.g. "Hallway A tablet"
    scopes: List[Literal["pendants.event", "locations.ingest", "wearables.event"]]
    secret_hash: str                       # bcrypt hash of the shared secret
    created_by: Optional[str] = None
    last_used_at: Optional[datetime] = None
    revoked: bool = False
    created_at: datetime = Field(default_factory=now_utc)


class DeviceTokenCreate(BaseModel):
    name: str
    scopes: List[Literal["pendants.event", "locations.ingest", "wearables.event"]] = Field(
        default_factory=lambda: ["pendants.event", "locations.ingest"]
    )


# ---------- Smart-room devices (IoT: AC, fan, heater, lights, TV, etc.) ----------
DeviceProtocol = Literal["bluetooth", "wifi", "rf_433", "rf_915", "ir", "zigbee", "matter"]
DeviceKind = Literal[
    "light", "fan", "heater", "ac", "thermostat", "tv", "speaker",
    "blinds", "outlet", "humidifier", "bed", "door_lock", "generic",
]
DeviceCapability = Literal[
    "power", "brightness", "temperature", "fan_speed", "volume",
    "channel", "color", "position",
]


class SmartDevice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    device_id: str = Field(default_factory=lambda: uid("dev"))
    label: str                              # human name, e.g. "Margaret's bedside lamp"
    kind: DeviceKind
    protocol: DeviceProtocol
    room: Optional[str] = None              # tied to resident's room by default
    resident_id: Optional[str] = None
    endpoint: Optional[str] = None          # MAC / IP / RF code / zigbee id
    capabilities: List[DeviceCapability] = Field(default_factory=list)
    state: dict = Field(default_factory=dict)   # e.g. {"power":"on","brightness":60,"temperature_c":22}
    vendor: Optional[str] = None
    model: Optional[str] = None
    online: bool = True
    last_command_at: Optional[datetime] = None
    notes: Optional[str] = ""
    created_at: datetime = Field(default_factory=now_utc)


class SmartDeviceCreate(BaseModel):
    label: str
    kind: DeviceKind
    protocol: DeviceProtocol
    room: Optional[str] = None
    resident_id: Optional[str] = None
    endpoint: Optional[str] = None
    capabilities: List[DeviceCapability] = Field(default_factory=list)
    vendor: Optional[str] = None
    model: Optional[str] = None
    notes: Optional[str] = ""


class DeviceCommandInput(BaseModel):
    """Action = the capability being set; value = the new value.

    Examples:
      {"action": "power",       "value": "off"}
      {"action": "temperature", "value": 22}
      {"action": "brightness",  "value": 60}
      {"action": "channel",     "value": "up"}
    """
    action: DeviceCapability
    value: Optional[str | int | float] = None


# ---------- AI vision ----------
class VisionFrameInput(BaseModel):
    """Base64-encoded JPEG from the glasses camera + optional spoken question."""
    image_base64: str
    question: Optional[str] = None      # if None → "describe what's in front of the person"
    resident_id: Optional[str] = None
    session_id: Optional[str] = None
    speak: bool = True                   # return TTS audio base64


class VisionSessionStart(BaseModel):
    resident_id: Optional[str] = None



# ---------- Staff tasks / daily work log ----------
# 2026-08-09 (Terminal 8): extended to also serve as the general resident
# request bus (nursing/maintenance/kitchen/front_desk/family/complaint),
# per "one source of truth, reuse existing models" - this was already a
# working, tested, role-assignable, status-tracked, timestamped domain
# object, so non-emergency resident requests route through it rather than
# a new parallel system. Safety/emergency stays on Alert, unchanged.
# Plain str, not a fixed Literal - internal staff-task categories (laundry,
# meds, meal, rounds, bathing, activity, transport, check_in, paperwork,
# other, family, complaint) are still the only options the admin "New
# task"/"New template" UI offers (see frontend/src/pages/TasksTab.jsx's
# own CATEGORIES list), but resident-request-bus categories now match
# whatever's in the admin-managed Department list (routes/departments.py),
# which can't be enumerated at the type level anymore.
TaskCategory = str
TaskStatus = Literal["pending", "in_progress", "completed", "skipped"]
TaskShift = Literal["day", "evening", "night", "any"]
TaskPriority = Literal["low", "normal", "high", "urgent"]
# Who/what originated this task/request - lets Aria-initiated and
# resident-initiated items be distinguished from staff-scheduled work.
TaskSource = Literal["staff", "aria_voice", "kiosk_button", "family", "system", "front_desk"]
# Coarse role gate for who should see this in their queue/dashboard.
# Enforced backend-side wherever tasks are listed for a given role - see
# ENGINEERING_CONTRACT.md (once written) for the authorization pattern.
# Plain str, not a fixed Literal - "all_staff"/"family" are the two
# special non-department values every caller still understands; anything
# else is expected to be a real Department.slug (routes/departments.py).
TaskVisibilityRole = str


class StaffTask(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_id: str = Field(default_factory=lambda: uid("task"))
    title: str
    description: Optional[str] = ""
    category: TaskCategory = "other"
    shift: TaskShift = "any"
    assigned_to: Optional[str] = None        # user_id of staff member
    assigned_name: Optional[str] = None      # denormalized for dashboard
    resident_id: Optional[str] = None        # optional — tied to a resident
    resident_name: Optional[str] = None
    room: Optional[str] = None
    status: TaskStatus = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None       # user_id of whoever closed it
    completed_by_name: Optional[str] = None
    duration_minutes: Optional[float] = None
    notes: Optional[str] = ""
    due_at: Optional[datetime] = None
    template_id: Optional[str] = None        # if spawned from a recurring template
    # ---- resident-request-bus fields (Terminal 8) ----
    priority: TaskPriority = "normal"
    source: TaskSource = "staff"
    visibility_role: TaskVisibilityRole = "all_staff"
    resident_words: Optional[str] = None     # verbatim quote, when resident-originated
    conversation_session_id: Optional[str] = None  # links back to the Aria session, if any
    acknowledged_by: Optional[str] = None
    acknowledged_by_name: Optional[str] = None  # denormalized, same pattern as assigned_name
    acknowledged_at: Optional[datetime] = None
    re_request_count: int = 0                # times a resident asked again before this closed
    last_re_requested_at: Optional[datetime] = None
    # Shared "when" field for any request type that needs a future time
    # instead of "now" (transportation today; nursing's "talk to my nurse
    # tomorrow" can reuse the same two fields later - build once, per the
    # Terminal 8 handoff's explicit instruction not to invent separate
    # incompatible time semantics per department).
    requested_for_date: Optional[str] = None       # YYYY-MM-DD, facility-local
    requested_for_time_label: Optional[str] = None  # staff/resident-friendly free text, e.g. "10:00 AM"
    # Transportation-specific: set once a TransportSlot is actually reserved.
    # verified_read/verified_control discipline: this field being set (plus
    # a "transportation_booked" receipt) is the ONLY thing that means
    # "booked" - an open slot existing is not a booking.
    transport_slot_id: Optional[str] = None
    # Resource-aware booking (driver+vehicle TransportRun) supersedes the
    # legacy hourly-bucket TransportSlot above for new bookings - see
    # transportation_engine.py. Both mean the same thing ("booked=true"
    # requires one of these to be set); slot_id is kept only so historical
    # pilot-seed data stays readable.
    transport_run_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)


class StaffTaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    category: TaskCategory = "other"
    shift: TaskShift = "any"
    assigned_to: Optional[str] = None
    resident_id: Optional[str] = None
    room: Optional[str] = None
    due_at: Optional[datetime] = None
    notes: Optional[str] = ""
    priority: TaskPriority = "normal"
    source: TaskSource = "staff"
    visibility_role: TaskVisibilityRole = "all_staff"
    resident_words: Optional[str] = None
    conversation_session_id: Optional[str] = None


class StaffTaskUpdate(BaseModel):
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[TaskStatus] = None
    acknowledged_by: Optional[str] = None


class StaffTaskTemplate(BaseModel):
    """Repeatable tasks — spun into real StaffTask rows each day/shift."""
    model_config = ConfigDict(extra="ignore")
    template_id: str = Field(default_factory=lambda: uid("ttpl"))
    title: str
    description: Optional[str] = ""
    category: TaskCategory = "other"
    shift: TaskShift = "any"
    resident_id: Optional[str] = None
    room: Optional[str] = None
    recur: Literal["daily", "weekly", "per_shift"] = "daily"
    active: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class StaffTaskTemplateCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    category: TaskCategory = "other"
    shift: TaskShift = "any"


# ---------- Operational receipts (Terminal 8) ----------
# One shared, generic receipt mechanism for meaningful actions across
# domains (task/request lifecycle, device commands, alerts, etc.), so the
# dashboard/staff/Aria/reporting/audit systems all read the same record
# instead of each domain inventing its own event log. A receipt points AT
# a domain object (related_object_type/id) rather than duplicating that
# object's own data - see backend/routes/receipts.py.
ReceiptStatus = Literal["created", "acknowledged", "in_progress", "completed", "failed", "cancelled"]


class Receipt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    receipt_id: str = Field(default_factory=lambda: uid("rcpt"))
    action_type: str                          # e.g. "task_created", "task_completed", "device_command"
    source: TaskSource = "system"
    resident_id: Optional[str] = None
    room: Optional[str] = None
    zone: Optional[str] = None
    conversation_session_id: Optional[str] = None  # Aria session, if Aria initiated this
    requested_by: Optional[str] = None         # user_id, "resident", or "aria"
    assigned_role: Optional[str] = None
    assigned_user: Optional[str] = None
    status: ReceiptStatus = "created"
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    failure_reason: Optional[str] = None
    follow_up_required: bool = False
    related_object_type: Optional[str] = None  # "task", "alert", "device_command", ...
    related_object_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)


# ---------- Schedule / activities (Terminal 8, resident-facing read lane) ----------
# Deliberately the lowest-stakes of the three planned inbound lanes (schedule,
# menu, transportation) - no request, no receipt, no routing, just a
# structured source Aria reads and answers from honestly. Staff-entered for
# now; an email/calendar adapter can feed this same model later without
# residents or Aria needing to know the difference.
ScheduleCategory = Literal["activity", "facility_note", "staff_hours"]


class ScheduleItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schedule_id: str = Field(default_factory=lambda: uid("sched"))
    date: str                                  # YYYY-MM-DD, facility-local
    time_label: Optional[str] = None           # staff-friendly free text, e.g. "2:00 PM"
    title: str
    description: Optional[str] = ""
    category: ScheduleCategory = "activity"
    source: str = "staff_entry"
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ScheduleItemCreate(BaseModel):
    date: str
    time_label: Optional[str] = None
    title: str
    description: Optional[str] = ""
    category: ScheduleCategory = "activity"


class ScheduleItemUpdate(BaseModel):
    date: Optional[str] = None
    time_label: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ScheduleCategory] = None


# ---------- Departments (admin-managed, replaces the old fixed StaffDepartment list) ----------
# One source of truth for "who can this route to" - staff pick their
# department from this list, resident-request categories validate against
# it, and Aria's tool schemas build their enum from it at session-mint
# time. Adding "therapy" or "resident programs" (or anything else) is an
# admin action now, not a code change + redeploy.
class Department(BaseModel):
    model_config = ConfigDict(extra="ignore")
    department_id: str = Field(default_factory=lambda: uid("dept"))
    slug: str                                   # stable machine key, set once at creation
    label: str                                  # display name, editable
    description: Optional[str] = ""
    contact_email: Optional[str] = None          # direct override for notify_department() -
    # prefer this over per-staff-user emails when a department is a shared
    # inbox (e.g. kitchen@facility) rather than individual logins.
    active: bool = True                          # soft-disable instead of hard delete
    created_at: datetime = Field(default_factory=now_utc)


class DepartmentCreate(BaseModel):
    label: str
    description: Optional[str] = ""
    contact_email: Optional[str] = None


class DepartmentUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    active: Optional[bool] = None


# ---------- Menu (Terminal 8, lane 2 - read pattern + a non-negotiable approval gate) ----------
# A wrong/hallucinated menu is a health-adjacent failure for a resident with
# a dietary restriction or diabetes, not just an annoyance - unlike the
# schedule lane, new items default to "draft" and Aria must NEVER read a
# draft item. Only "approved" items are ever exposed via the public
# endpoint. This gate is exercised now with staff-typed entries so it's
# already proven correct before an email-ingestion adapter (future work)
# starts feeding this same model with less-trusted, AI-parsed content.
MealPeriod = Literal["breakfast", "lunch", "dinner"]
# "superseded" - a later upload replaced this item's whole (date, meal_period)
# batch. Kept for history/provenance, permanently excluded from the public
# read Aria uses - "Aria should always read the current approved version."
MenuItemStatus = Literal["draft", "approved", "superseded"]


class MenuItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    menu_id: str = Field(default_factory=lambda: uid("menu"))
    date: str                                  # YYYY-MM-DD, facility-local (service_date)
    meal_period: MealPeriod
    item_name: str
    description: Optional[str] = ""
    availability: Optional[str] = None          # e.g. "always available", "while supplies last"
    status: MenuItemStatus = "draft"
    source: str = "staff_entry"                 # "staff_entry" | "email_dev_test" (future: "email")
    upload_id: Optional[str] = None             # links back to the MenuUpload batch that created it, if any
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class MenuItemCreate(BaseModel):
    date: str
    meal_period: MealPeriod
    item_name: str
    description: Optional[str] = ""
    availability: Optional[str] = None


class MenuItemUpdate(BaseModel):
    date: Optional[str] = None
    meal_period: Optional[MealPeriod] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    availability: Optional[str] = None


# ---------- Menu ingestion (email adapter boundary) ----------
# One upload = one ingestion event (today: a simulated dev-test email body;
# future: a real inbound email). Preserves the raw source so staff can see
# exactly what was parsed and why, and groups the MenuItem rows it produced
# so approving "today's menu email" is one action, not N. The email/mailbox
# itself is never the source of truth - this record + the MenuItems it
# produced are; email is transport only, per the architecture decision.
MenuUploadParseStatus = Literal["parsed", "needs_review"]
MenuUploadStatus = Literal["draft", "approved"]


class MenuUpload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    upload_id: str = Field(default_factory=lambda: uid("mupload"))
    source: str = "email_dev_test"              # future: "email"
    source_ref: Optional[str] = None            # simulated message id / filename
    raw_text: str = ""                          # preserved body, truncated at ingest time
    service_date: str                           # YYYY-MM-DD this upload is for
    parse_status: MenuUploadParseStatus = "parsed"
    parse_notes: Optional[str] = None
    status: MenuUploadStatus = "draft"
    item_ids: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None            # None for automated ingestion
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)


# ---------- Transportation availability (Terminal 8, lane 3 - separate from the request itself) ----------
# Deliberately its own record, distinct from the request/receipt bus:
# availability is a capacity ledger CAOSCare owns and can write to (this is
# the Michael-controlled-calendar case from the handoff, simulated here as
# an internal schedule until real calendar sync is built - see the living
# build log for that boundary). A request (StaffTask) POINTS AT a slot via
# transport_slot_id once reserved; the slot doesn't know about the
# resident, keeping "availability / request / booking" as separate
# concerns per the directive's own architecture rule.
class TransportSlot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    slot_id: str = Field(default_factory=lambda: uid("tslot"))
    date: str                                  # YYYY-MM-DD, facility-local
    start_time: str                            # "08:00" 24h, facility-local
    end_time: str                              # "09:00"
    capacity: int = 1
    booked_count: int = 0
    source: str = "internal_schedule"          # future: "outlook_calendar"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


# ---------- Resident memory (long-term learned facts) ----------
MemoryCategory = Literal[
    "family", "preferences", "health", "history", "daily_pattern",
    "concern", "relationship", "milestone", "other",
]

# Two bins drive hydration:
#   facts  = durable identity (family, preferences, health, daily patterns, relationships, history)
#   events = dated moments (concerns, milestones, significant conversations)
MemoryBin = Literal["facts", "events"]

_FACTS_CATEGORIES = {"family", "preferences", "health", "history", "daily_pattern", "relationship"}


def default_bin_for_category(category: str) -> str:
    return "facts" if category in _FACTS_CATEGORIES else "events"


class ResidentMemory(BaseModel):
    """One discrete fact or life-event CAOS has learned about a resident.
    Pulled into every chat so the AI remembers across sessions and grows
    with the resident over time. See /admin/blueprint for the full model."""
    model_config = ConfigDict(extra="ignore")
    memory_id: str = Field(default_factory=lambda: uid("mem"))
    resident_id: str
    text: str                                              # the fact itself
    category: MemoryCategory = "other"
    bin: MemoryBin = "facts"                               # which bulletin bin it lives in
    importance: int = 3                                    # 1=minor, 5=critical to remember
    source: Literal["chat", "admin", "staff", "family", "extraction"] = "extraction"
    source_session: Optional[str] = None
    event_at: Optional[datetime] = None                    # when the event happened (events bin)
    last_referenced_at: Optional[datetime] = None
    times_referenced: int = 0
    pinned: bool = False                                   # admin-pinned memories never drop out
    archived: bool = False                                 # dehydrated / retired but retained
    created_at: datetime = Field(default_factory=now_utc)


class ResidentMemoryCreate(BaseModel):
    resident_id: str
    text: str
    category: MemoryCategory = "other"
    bin: Optional[MemoryBin] = None                         # auto-derived from category if omitted
    importance: int = 3
    source: Literal["chat", "admin", "staff", "family", "extraction"] = "admin"
    pinned: bool = False
    event_at: Optional[datetime] = None


class ResidentMemoryUpdate(BaseModel):
    text: Optional[str] = None
    category: Optional[MemoryCategory] = None
    bin: Optional[MemoryBin] = None
    importance: Optional[int] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    event_at: Optional[datetime] = None



# ---------- RF Pairing & Reception (sub-GHz SDR) ----------

# A unique fingerprint of a sub-GHz button press. The kiosk's USB SDR captures
# the air, demodulates whatever protocol it can, and reduces it to these fields.
class RFFingerprint(BaseModel):
    frequency_hz: int                                     # e.g. 319_000_000
    modulation: Literal["OOK", "ASK", "FSK", "PWM", "unknown"] = "unknown"
    bit_pattern_hex: str                                  # decoded payload, hex
    bit_length: int                                       # length of bit_pattern in bits
    rssi: Optional[float] = None                          # received signal strength (dBm-ish)


# A paired device — bound to a resident and assigned a severity. Future
# presses that match this fingerprint auto-fire alerts.
class RFDevice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rf_device_id: str = Field(default_factory=lambda: uid("rfd"))
    label: str                                            # "Margaret's bedside pendant"
    resident_id: Optional[str] = None
    room: Optional[str] = None
    fingerprint: RFFingerprint
    severity: Literal["help", "assist", "emergency", "comfort"] = "help"
    match_threshold: float = 0.85                         # min similarity 0..1
    enabled: bool = True
    last_seen_at: Optional[datetime] = None
    last_rssi: Optional[float] = None
    press_count: int = 0
    low_battery: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    created_by: Optional[str] = None


# A pairing capture window — the kiosk listens for ~10s, pushes whatever
# it heard back here. Admin then turns it into an RFDevice via /pair.
class RFCapture(BaseModel):
    model_config = ConfigDict(extra="ignore")
    capture_id: str = Field(default_factory=lambda: uid("cap"))
    kiosk_id: str
    requested_by: Optional[str] = None
    bands: List[int] = Field(default_factory=list)        # frequencies to scan (Hz)
    status: Literal["pending", "listening", "captured", "timeout", "cancelled"] = "pending"
    captured: Optional[RFFingerprint] = None
    started_at: datetime = Field(default_factory=now_utc)
    expires_at: datetime
    completed_at: Optional[datetime] = None


class RFListenStart(BaseModel):
    kiosk_id: str
    duration_seconds: int = 10                            # capture window length
    bands: Optional[List[int]] = None                     # default profile if omitted


class RFPair(BaseModel):
    capture_id: str
    label: str
    resident_id: Optional[str] = None
    severity: Literal["help", "assist", "emergency", "comfort"] = "help"
    match_threshold: float = 0.85


# Bridge → backend. Fired every time the SDR sees a known-or-unknown press.
# HMAC signed (header X-RF-Signature). Backend matches against db.rf_devices
# and either fires an alert or logs as unmatched.
class RFEventIn(BaseModel):
    kiosk_id: str
    fingerprint: RFFingerprint
    sequence: int                                         # monotonic, replay protection
    captured_at: Optional[datetime] = None



# ---------- Device Class doctrine (Blueprint [INF-004]) ----------
# The capability-probe pipeline:
#     Device Class → Capability Profile → Compatibility Probe →
#     Hardware Receipt → Deployment Role → Admin Blueprint Stack

DeviceClassEnum = Literal[
    "kiosk_tablet", "caos_hub", "speaker_node",
    "linux_bridge", "wearable_gateway", "wall_terminal",
]

DeploymentRoleEnum = Literal[
    "room_companion", "pendant_gateway", "staff_pager_hub",
    "lobby_kiosk", "medication_station",
]

CapabilityKey = Literal[
    "far_field_mic", "speaker_quality", "wifi_ac", "persistent_power",
    "haptic_feedback", "usb_host", "bluetooth_le", "mesh_radio_subghz",
    "camera", "battery_min_hours", "touchscreen", "display_resolution_min",
]


class CapabilityProfile(BaseModel):
    """The capability requirements declared by a Device Class. Required
    capabilities must pass; optional ones are nice-to-have."""
    model_config = ConfigDict(extra="ignore")
    device_class: DeviceClassEnum
    required: List[CapabilityKey] = Field(default_factory=list)
    optional: List[CapabilityKey] = Field(default_factory=list)


class ProbeResult(BaseModel):
    capability: CapabilityKey
    result: Literal["pass", "fail", "not_tested"] = "not_tested"
    measurement: Optional[str] = None      # e.g. "SNR 28 dB @ 3m"
    measured_at: Optional[datetime] = None


class HardwareDevice(BaseModel):
    """A piece of hardware in the field — claimed by class, role-assigned
    only after a passing receipt."""
    model_config = ConfigDict(extra="ignore")
    hw_id: str = Field(default_factory=lambda: uid("hw"))
    facility_id: Optional[str] = None
    device_class: DeviceClassEnum
    serial: Optional[str] = None
    model_name: Optional[str] = None
    deployment_role: Optional[DeploymentRoleEnum] = None
    deployment_room: Optional[str] = None
    last_receipt_id: Optional[str] = None
    last_receipt_status: Literal["none", "pass", "fail", "expired"] = "none"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)


class HardwareDeviceCreate(BaseModel):
    facility_id: Optional[str] = None
    device_class: DeviceClassEnum
    serial: Optional[str] = None
    model_name: Optional[str] = None
    deployment_room: Optional[str] = None
    notes: Optional[str] = None


class HardwareReceipt(BaseModel):
    """Signed, timestamped certificate of probe results. Required before a
    device can be assigned a deployment_role. Valid for 90 days."""
    model_config = ConfigDict(extra="ignore")
    receipt_id: str = Field(default_factory=lambda: uid("hwr"))
    hw_id: str
    facility_id: Optional[str] = None
    device_class: DeviceClassEnum
    probes: List[ProbeResult] = Field(default_factory=list)
    overall: Literal["pass", "fail"] = "fail"
    issued_at: datetime = Field(default_factory=now_utc)
    expires_at: datetime
    signature: Optional[str] = None
    issued_by: Optional[str] = None


class ProbeRequest(BaseModel):
    hw_id: str
    probes: List[ProbeResult]


class RoleAssignment(BaseModel):
    hw_id: str
    deployment_role: DeploymentRoleEnum
    deployment_room: Optional[str] = None


# ---------- Escalation rules (auto-escalate unacknowledged alerts) ----------
class EscalationRule(BaseModel):
    """Per-facility config: how long before an unacknowledged alert escalates,
    and to whom. Levels match the Blueprint [RS-002] flow:
      Level 1 → all staff (already happens on alert.create)
      Level 2 → staff + supervisor after `level_2_seconds`
      Level 3 → staff + supervisor + on-call medical after `level_3_seconds`."""
    model_config = ConfigDict(extra="ignore")
    facility_id: Optional[str] = None
    level_2_seconds: int = 90
    level_3_seconds: int = 150
    notify_supervisor_phone: Optional[str] = None
    notify_oncall_phone: Optional[str] = None
    enabled: bool = True
    updated_at: datetime = Field(default_factory=now_utc)


# ---------- Aria capability portfolio (Terminal 5A) ----------
# A durable registry of every device/service/workflow/tool Aria may ever
# control, so capability is never lost between sessions and Aria never
# claims control she doesn't actually have. See docs/ARIA_CAPABILITY_PORTFOLIO.md.

CapabilityLifecycle = Literal[
    "planned", "discovered", "configured", "verified_read",
    "verified_control", "blocked", "offline", "retired",
]

CapabilityCategory = Literal[
    "voice", "memory", "home_automation", "appliance", "messaging",
    "infrastructure", "hardware", "future",
]


class AriaCapability(BaseModel):
    """One entry in the capability portfolio. Aria may only claim to control
    a capability when status == 'verified_control' AND the requested action
    is in supported_actions."""
    model_config = ConfigDict(extra="ignore")
    capability_id: str = Field(default_factory=lambda: uid("cap"))
    name: str
    category: CapabilityCategory = "future"
    target: str                                    # device/service/workflow/system this acts on
    discovery_source: str                           # how we know this exists (doc, host scan, directive)
    status: CapabilityLifecycle = "planned"
    control_path: Optional[str] = None              # API route / MQTT topic / CLI, etc.
    required_credentials: List[str] = Field(default_factory=list)   # env var NAMES only, never values
    supported_actions: List[str] = Field(default_factory=list)
    read_only_observations: List[str] = Field(default_factory=list)
    verification_state: Optional[str] = None        # free-text: how/when last verified
    last_verified_at: Optional[datetime] = None
    current_blocker: Optional[str] = None
    next_step: Optional[str] = None
    human_confirmation_policy: Literal["always_confirm", "confirm_destructive", "autonomous"] = "always_confirm"
    receipt_log_location: str = "db.aria_capability_receipts"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class AriaCapabilityCreate(BaseModel):
    name: str
    category: CapabilityCategory = "future"
    target: str
    discovery_source: str
    status: CapabilityLifecycle = "planned"
    control_path: Optional[str] = None
    required_credentials: List[str] = Field(default_factory=list)
    supported_actions: List[str] = Field(default_factory=list)
    read_only_observations: List[str] = Field(default_factory=list)
    current_blocker: Optional[str] = None
    next_step: Optional[str] = None
    human_confirmation_policy: Literal["always_confirm", "confirm_destructive", "autonomous"] = "always_confirm"


class AriaCapabilityUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[CapabilityCategory] = None
    target: Optional[str] = None
    status: Optional[CapabilityLifecycle] = None
    control_path: Optional[str] = None
    required_credentials: Optional[List[str]] = None
    supported_actions: Optional[List[str]] = None
    read_only_observations: Optional[List[str]] = None
    current_blocker: Optional[str] = None
    next_step: Optional[str] = None
    human_confirmation_policy: Optional[Literal["always_confirm", "confirm_destructive", "autonomous"]] = None


class AriaCapabilityVerify(BaseModel):
    """Records a verification attempt against a capability — this IS the
    receipt (persisted to db.aria_capability_receipts)."""
    outcome: Literal["verified_read", "verified_control", "blocked", "offline"]
    note: Optional[str] = None


# ---------- Aria operator memory (NOT resident memory) ----------
# Deliberately separate from ResidentMemory / docs/CAOSCARE_MEMORY_AUTOMATION_CONTRACT.md.
# That system stores elder-care facts about a resident_id under a governed,
# clinical-adjacent contract. Aria's operator memory stores Michael's own
# identity/preferences/projects and is scoped to owner_user_id, never mixed
# into resident bulletins, extraction, or facility-facing views.

AriaMemoryCategory = Literal[
    "identity", "preference", "project", "commitment", "decision",
    "session_summary", "other",
]
AriaMemoryBin = Literal["standing", "episodic"]
AriaMemoryConfidence = Literal["stated", "inferred", "uncertain"]

_ARIA_STANDING_CATEGORIES = {"identity", "preference", "project"}


def default_aria_bin_for_category(category: str) -> str:
    return "standing" if category in _ARIA_STANDING_CATEGORIES else "episodic"


class AriaMemory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    memory_id: str = Field(default_factory=lambda: uid("amem"))
    owner_user_id: str
    text: str
    category: AriaMemoryCategory = "other"
    bin: AriaMemoryBin = "standing"
    importance: int = 3
    source: Literal["voice_session", "chat", "admin", "extraction"] = "extraction"
    source_session_id: Optional[str] = None
    confidence: AriaMemoryConfidence = "stated"
    pinned: bool = False
    archived: bool = False
    last_referenced_at: Optional[datetime] = None
    times_referenced: int = 0
    created_at: datetime = Field(default_factory=now_utc)


class AriaMemoryCreate(BaseModel):
    owner_user_id: str
    text: str
    category: AriaMemoryCategory = "other"
    bin: Optional[AriaMemoryBin] = None
    importance: int = 3
    source: Literal["voice_session", "chat", "admin", "extraction"] = "admin"
    confidence: AriaMemoryConfidence = "stated"
    pinned: bool = False


class AriaMemoryUpdate(BaseModel):
    text: Optional[str] = None
    category: Optional[AriaMemoryCategory] = None
    bin: Optional[AriaMemoryBin] = None
    importance: Optional[int] = None
    confidence: Optional[AriaMemoryConfidence] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None


class AriaVoiceSession(BaseModel):
    """Session summary/receipt written at the end of every Aria voice
    session. Never stores raw audio."""
    model_config = ConfigDict(extra="ignore")
    session_id: str = Field(default_factory=lambda: uid("avs"))
    owner_user_id: str
    wake_word: str = "Aria"
    transport: Literal["openai_realtime", "local_fallback"] = "openai_realtime"
    started_at: datetime = Field(default_factory=now_utc)
    ended_at: Optional[datetime] = None
    topics: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    tasks_created: List[str] = Field(default_factory=list)
    tasks_completed: List[str] = Field(default_factory=list)
    unresolved_next_step: Optional[str] = None
    tool_actions: List[dict] = Field(default_factory=list)   # {capability_id, action, result, receipt_ref}


class AriaVoiceSessionCreate(BaseModel):
    owner_user_id: str
    wake_word: str = "Aria"
    transport: Literal["openai_realtime", "local_fallback"] = "openai_realtime"


class AriaVoiceSessionEnd(BaseModel):
    topics: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    tasks_created: List[str] = Field(default_factory=list)
    tasks_completed: List[str] = Field(default_factory=list)
    unresolved_next_step: Optional[str] = None
    tool_actions: List[dict] = Field(default_factory=list)
