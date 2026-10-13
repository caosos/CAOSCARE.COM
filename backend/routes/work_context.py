"""Owner/admin Work-as boundary for ordinary department work.

The browser keeps the signed token in session storage and sends it only in
``X-CAOS-Work-Context``.  Authentication still resolves the real principal;
this dependency adds a short-lived, department-scoped authorization view for
the routes that explicitly opt in.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user
from routes.departments import get_active_departments
from simulation.work_context import WorkContextError, effective_user, issue, resolve


router = APIRouter(prefix="/work-context", tags=["work-context"])
HEADER = "X-CAOS-Work-Context"


class WorkContextInput(BaseModel):
    acting_role: str = "staff"
    acting_department: str


async def _active() -> list[dict]:
    return await get_active_departments()


def _http_error(exc: WorkContextError) -> HTTPException:
    status = 403 if exc.code in {"principal_not_admin", "principal_mismatch"} else 400
    if exc.code in {"expired_context", "invalid_token", "missing_token"}:
        status = 401
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


async def _resolve_header(token: str, principal: dict):
    departments = await _active()
    try:
        context = resolve(token, principal, known_departments=[d["slug"] for d in departments])
    except WorkContextError as exc:
        raise _http_error(exc) from exc
    return context, departments


async def get_department_user(
    request: Request,
    work_token: str | None = Header(default=None, alias=HEADER),
):
    """Normal principal, or a validated Work-as view on opted-in routes."""
    principal = await get_current_user(request)
    if not work_token:
        return principal
    context, _ = await _resolve_header(work_token, principal)
    return effective_user(principal, context)


@router.get("/options")
async def options(principal=Depends(get_current_user)):
    if principal.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return {
        "departments": await _active(),
        "roles": [
            {"role": "staff", "department": "*"},
            {"role": "front_desk", "department": "administration"},
        ],
    }


@router.post("")
async def create_context(data: WorkContextInput, principal=Depends(get_current_user)):
    departments = await _active()
    try:
        token, context = issue(
            principal,
            acting_role=data.acting_role,
            acting_department=data.acting_department,
            known_departments=[d["slug"] for d in departments],
        )
    except WorkContextError as exc:
        raise _http_error(exc) from exc
    return {"token": token, "context": _view(context)}


@router.get("/current")
async def current_context(
    principal=Depends(get_current_user),
    work_token: str | None = Header(default=None, alias=HEADER),
):
    if not work_token:
        raise HTTPException(status_code=401, detail="Work context is not active")
    context, _ = await _resolve_header(work_token, principal)
    return _view(context)


def _view(context) -> dict:
    return {
        "work_context_id": context.context_id,
        "principal_id": context.principal_id,
        "principal_role": context.principal_role,
        "acting_role": context.acting_role,
        "acting_department": context.acting_department,
        "issued_at": context.issued_at,
        "expires_at": context.expires_at,
    }
