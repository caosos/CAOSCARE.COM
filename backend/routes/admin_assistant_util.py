"""Tiny shared helpers for the admin-assistant tool executors - kept
separate from admin_assistant_executor.py/admin_assistant_ui_executor.py
purely to avoid a circular import between them.
"""
import re

_ROOM_PREFIX = re.compile(r"^\s*room\s+", re.IGNORECASE)


def normalize_room(room: str | None) -> str | None:
    """The model sometimes passes a human label like 'Room 214' instead of
    the bare identifier '214' actually stored on residents/kiosks/devices
    (confirmed live, 2026-08-27 - a real query silently matched nothing
    because of this). Strip a leading 'room ' so tools stay robust to how
    the model phrases it, rather than requiring the model to get this
    exactly right every time."""
    if not room:
        return room
    return _ROOM_PREFIX.sub("", room).strip()
