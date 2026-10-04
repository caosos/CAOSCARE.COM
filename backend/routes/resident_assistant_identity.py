"""The resident-facing assistant's spoken name — one source for the backend.

Default "Aria" (unchanged behaviour). A test environment may set
CAOSCARE_RESIDENT_ASSISTANT_NAME (e.g. "Jarvis") so the resident hears and
sees only that one name. The resident prompt and the session context both
read it from here; the room screen shows the name the session returns.
"""
import os
import re

DEFAULT_NAME = "Aria"
_VALID = re.compile(r"^[A-Za-z][A-Za-z' -]{0,23}$")


def assistant_name() -> str:
    name = (os.environ.get("CAOSCARE_RESIDENT_ASSISTANT_NAME") or "").strip()
    return name if _VALID.match(name) else DEFAULT_NAME
