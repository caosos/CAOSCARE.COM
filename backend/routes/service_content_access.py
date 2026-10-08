"""Who may change resident-facing community content (menu, activities
schedule). Owner/admin always; a plain `staff` user only when their
Department owns that content - Kitchen for the menu, Activities for the
schedule - or is Administration. Same department scoping the task queues
use (Product Baseline section 4), applied to the two content lanes.
"""
from fastapi import HTTPException

MENU_DEPARTMENTS = {"kitchen", "administration"}
SCHEDULE_DEPARTMENTS = {"activities", "administration"}


def can_edit_content(user: dict, departments: set[str]) -> bool:
    role = user.get("role")
    if role in ("owner", "admin"):
        return True
    return role == "staff" and user.get("department") in departments


def require_content_editor(user: dict, departments: set[str]) -> None:
    if not can_edit_content(user, departments):
        raise HTTPException(status_code=403, detail="Only this department's staff or an administrator can change this")
