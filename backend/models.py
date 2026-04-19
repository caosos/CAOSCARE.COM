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
    created_at: datetime = Field(default_factory=now_utc)


class ResidentCreate(BaseModel):
    name: str
    room: str
    pendant_id: str
    photo: Optional[str] = None
    medical_notes: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    date_of_birth: Optional[str] = None


# ---------- Kiosks / Zones ----------
class Kiosk(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kiosk_id: str = Field(default_factory=lambda: uid("kio"))
    name: str
    room: str
    zone: str
    mac_address: Optional[str] = None
    status: Literal["online", "offline"] = "online"
    created_at: datetime = Field(default_factory=now_utc)


class KioskCreate(BaseModel):
    name: str
    room: str
    zone: str
    mac_address: Optional[str] = None


class Zone(BaseModel):
    model_config = ConfigDict(extra="ignore")
    zone_id: str = Field(default_factory=lambda: uid("zone"))
    name: str
    floor: Optional[str] = None
    description: Optional[str] = ""
    created_at: datetime = Field(default_factory=now_utc)


class ZoneCreate(BaseModel):
    name: str
    floor: Optional[str] = None
    description: Optional[str] = ""


# ---------- Alerts ----------
AlertSeverity = Literal["emergency", "assist", "comfort"]
AlertStatus = Literal["active", "acknowledged", "resolved"]


class Alert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    alert_id: str = Field(default_factory=lambda: uid("alert"))
    kiosk_id: Optional[str] = None
    resident_id: Optional[str] = None
    resident_name: Optional[str] = None
    room: Optional[str] = None
    zone: Optional[str] = None
    severity: AlertSeverity = "assist"
    status: AlertStatus = "active"
    message: Optional[str] = ""
    triggered_by: Literal["kiosk_button", "ai_triage", "pendant", "manual"] = "kiosk_button"
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)


class AlertCreate(BaseModel):
    kiosk_id: Optional[str] = None
    resident_id: Optional[str] = None
    severity: AlertSeverity = "assist"
    message: Optional[str] = ""
    triggered_by: Literal["kiosk_button", "ai_triage", "pendant", "manual"] = "kiosk_button"


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
