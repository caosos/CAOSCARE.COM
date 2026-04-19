from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid


def uid(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Users (staff / admin) ----------
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str = Field(default_factory=lambda: uid("user"))
    email: str
    name: str
    role: Literal["admin", "staff"] = "staff"
    picture: Optional[str] = None
    auth_provider: Literal["jwt", "google"] = "jwt"
    password_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)


class UserPublic(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    picture: Optional[str] = None
    auth_provider: str


class RegisterInput(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: Literal["admin", "staff"] = "staff"


class LoginInput(BaseModel):
    email: EmailStr
    password: str


# ---------- Residents ----------
ParticipationLevel = Literal["room_only", "pendant_enhanced", "wearable_enhanced", "family_connected", "full"]


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
    triggered_by: Literal["kiosk_button", "ai_triage", "pendant", "manual", "geofence", "wearable"] = "kiosk_button"
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    outcome: Optional[str] = None      # e.g. "assisted to bathroom"
    close_notes: Optional[str] = None
    auto_voice: bool = False             # hands-free mic activation on kiosk (panic-press / fall)
    press_count: int = 1                 # how many rapid presses triggered this
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
TaskCategory = Literal[
    "laundry", "meds", "meal", "rounds", "bathing", "housekeeping",
    "activity", "transport", "check_in", "paperwork", "other",
]
TaskStatus = Literal["pending", "in_progress", "completed", "skipped"]
TaskShift = Literal["day", "evening", "night", "any"]


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


class StaffTaskUpdate(BaseModel):
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[TaskStatus] = None


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


# ---------- Resident memory (long-term learned facts) ----------
MemoryCategory = Literal[
    "family", "preferences", "health", "history", "daily_pattern",
    "concern", "relationship", "milestone", "other",
]


class ResidentMemory(BaseModel):
    """One discrete fact CAOS has learned (or been told) about a resident.
    These are pulled into every chat so the AI remembers across sessions and
    stays a trusted companion that grows with the resident over time."""
    model_config = ConfigDict(extra="ignore")
    memory_id: str = Field(default_factory=lambda: uid("mem"))
    resident_id: str
    text: str                                              # the fact itself
    category: MemoryCategory = "other"
    importance: int = 3                                    # 1=minor, 5=critical to remember
    source: Literal["chat", "admin", "staff", "family", "extraction"] = "extraction"
    source_session: Optional[str] = None
    last_referenced_at: Optional[datetime] = None
    times_referenced: int = 0
    pinned: bool = False                                   # admin-pinned memories never drop out
    created_at: datetime = Field(default_factory=now_utc)


class ResidentMemoryCreate(BaseModel):
    resident_id: str
    text: str
    category: MemoryCategory = "other"
    importance: int = 3
    source: Literal["chat", "admin", "staff", "family", "extraction"] = "admin"
    pinned: bool = False


class ResidentMemoryUpdate(BaseModel):
    text: Optional[str] = None
    category: Optional[MemoryCategory] = None
    importance: Optional[int] = None
    pinned: Optional[bool] = None
