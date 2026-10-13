"""Signed, short-lived owner/admin work context.

This module deliberately has no HTTP, database, or UI behavior. Routes can
later use it to let a real administrator enter a department-scoped workspace
without changing their account or impersonating an employee.

The authenticated principal always remains the actor. ``acting_role`` and
``acting_department`` are separate authorization context and separate receipt
metadata. Callers must supply the current active department slugs both when a
context is issued and when it is resolved, so a removed/deactivated department
fails closed even if an older token is still cryptographically valid.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from typing import Collection, Optional
import uuid

import jwt


ALGORITHM = "HS256"
AUDIENCE = "caoscare-work-context"
ISSUER = "caoscare"
CONTEXT_TYPE = "admin_work_context"
ADMIN_ROLES = frozenset({"owner", "admin"})
ACTING_ROLES = frozenset({"staff", "front_desk"})
DEFAULT_TTL_SECONDS = 2 * 60 * 60
MAX_TTL_SECONDS = 4 * 60 * 60


class WorkContextError(ValueError):
    """A context that must not be issued or trusted."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WorkContext:
    context_id: str
    principal_id: str
    principal_role: str
    acting_role: str
    acting_department: str
    issued_at: int
    expires_at: int

    def claims(self) -> dict:
        return {
            "context_type": CONTEXT_TYPE,
            "sub": self.principal_id,
            "principal_role": self.principal_role,
            "acting_role": self.acting_role,
            "acting_department": self.acting_department,
            "jti": self.context_id,
            "iat": self.issued_at,
            "exp": self.expires_at,
            "aud": AUDIENCE,
            "iss": ISSUER,
        }


def _secret(explicit: Optional[str]) -> str:
    value = explicit or os.environ.get("JWT_SECRET", "")
    if not value:
        raise WorkContextError("missing_secret", "Work-context signing secret is not configured")
    return value


def _principal(principal: dict) -> tuple[str, str]:
    user_id = str(principal.get("user_id") or "").strip()
    role = str(principal.get("role") or "").strip()
    if not user_id or role not in ADMIN_ROLES:
        raise WorkContextError("principal_not_admin", "An authenticated owner or admin is required")
    return user_id, role


def _department(value: str, known_departments: Collection[str]) -> str:
    department = str(value or "").strip()
    if not department or department not in set(known_departments):
        raise WorkContextError("unknown_department", "Acting department is not an active department")
    return department


def _acting_scope(role: str, department: str, known_departments: Collection[str]) -> tuple[str, str]:
    acting_role = str(role or "").strip()
    if acting_role not in ACTING_ROLES:
        raise WorkContextError("unknown_role", "Acting role is not allowed")
    acting_department = _department(department, known_departments)
    if acting_role == "front_desk" and acting_department != "administration":
        raise WorkContextError("invalid_scope", "Front desk may act only for Administration")
    return acting_role, acting_department


def issue(
    principal: dict,
    *,
    acting_role: str,
    acting_department: str,
    known_departments: Collection[str],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    secret: Optional[str] = None,
    now: Optional[datetime] = None,
) -> tuple[str, WorkContext]:
    """Validate and sign one work context; never modifies ``principal``."""
    principal_id, principal_role = _principal(principal)
    role, department = _acting_scope(acting_role, acting_department, known_departments)
    if not isinstance(ttl_seconds, int) or ttl_seconds < 60 or ttl_seconds > MAX_TTL_SECONDS:
        raise WorkContextError("invalid_ttl", "Work context must last between 60 seconds and 4 hours")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise WorkContextError("invalid_time", "Work-context time must be timezone-aware")
    issued_at = int(current.timestamp())
    context = WorkContext(
        context_id=f"wctx_{uuid.uuid4().hex[:16]}",
        principal_id=principal_id,
        principal_role=principal_role,
        acting_role=role,
        acting_department=department,
        issued_at=issued_at,
        expires_at=int((current + timedelta(seconds=ttl_seconds)).timestamp()),
    )
    return jwt.encode(context.claims(), _secret(secret), algorithm=ALGORITHM), context


def resolve(
    token: str,
    principal: dict,
    *,
    known_departments: Collection[str],
    secret: Optional[str] = None,
) -> WorkContext:
    """Verify signature, expiry, principal binding and current acting scope."""
    principal_id, principal_role = _principal(principal)
    if not token:
        raise WorkContextError("missing_token", "Work-context token is required")
    try:
        claims = jwt.decode(
            token,
            _secret(secret),
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["sub", "principal_role", "acting_role", "acting_department", "jti", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise WorkContextError("expired_context", "Work context has expired") from exc
    except jwt.PyJWTError as exc:
        raise WorkContextError("invalid_token", "Work-context token is invalid") from exc

    if claims.get("context_type") != CONTEXT_TYPE:
        raise WorkContextError("invalid_token", "Token is not a CAOSCare work context")
    if claims.get("sub") != principal_id or claims.get("principal_role") != principal_role:
        raise WorkContextError("principal_mismatch", "Work context belongs to a different principal")
    role, department = _acting_scope(
        claims.get("acting_role"), claims.get("acting_department"), known_departments
    )
    return WorkContext(
        context_id=str(claims["jti"]),
        principal_id=principal_id,
        principal_role=principal_role,
        acting_role=role,
        acting_department=department,
        issued_at=int(claims["iat"]),
        expires_at=int(claims["exp"]),
    )


def effective_user(principal: dict, context: WorkContext) -> dict:
    """Return staff-scoped authorization data while retaining principal facts."""
    principal_id, principal_role = _principal(principal)
    if context.principal_id != principal_id or context.principal_role != principal_role:
        raise WorkContextError("principal_mismatch", "Work context belongs to a different principal")
    return {
        **principal,
        "role": context.acting_role,
        "department": context.acting_department,
        "_principal_role": principal_role,
        "_principal_department": principal.get("department"),
        "_work_context_id": context.context_id,
        "_work_context_acting_role": context.acting_role,
        "_work_context_acting_department": context.acting_department,
    }


def receipt_metadata(principal: dict, context: WorkContext, *, channel: str = "staff_ui") -> dict:
    """Dual provenance: real authenticated actor plus temporary acting seat."""
    principal_id, principal_role = _principal(principal)
    if context.principal_id != principal_id or context.principal_role != principal_role:
        raise WorkContextError("principal_mismatch", "Work context belongs to a different principal")
    return {
        "actor_id": principal_id,
        "actor_type": "real-human",
        "actor_name": principal.get("name"),
        "actor_role": principal_role,
        "actor_department": principal.get("department"),
        "acting_role": context.acting_role,
        "acting_department": context.acting_department,
        "work_context_id": context.context_id,
        "channel": channel,
        "identity_basis": "authenticated",
        "simulated": False,
    }


def scoped_authority(base: str, context: WorkContext) -> str:
    """Name both the admin grant and the ordinary staff rule being exercised."""
    return (
        f"admin_work_as:{context.principal_role}:as:{context.acting_role}:"
        f"{context.acting_department}:{base}"
    )
