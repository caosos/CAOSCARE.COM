"""Parse a planned time label ("10:00 AM", "2-4 PM", "around 3 pm", "14:30")
into minutes after midnight for ORDERING and OVERLAP checks only. Shared by
the upcoming view and the conflict check so both read a label the same way.
UNTIMED means no clock time could be read; callers must say so, never guess."""
import re
from typing import Optional

UNTIMED = 24 * 60 + 1          # sorts after every real clock time of the day
_CLOCK = re.compile(r"(?<!\d)(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\b", re.I)
_CLOCK_24 = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\s*[ap])", re.I)
_RANGE = re.compile(r"\s*(\d{1,2})(?::(\d{2}))?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*([ap])\.?\s*m\b", re.I)


def _h12(h: int, mm: int, ap: str) -> int:
    return (h % 12 + (12 if ap == "p" else 0)) * 60 + mm


def time_minutes(label: Optional[str]) -> int:
    """Minutes after midnight for the FIRST clock time in a free-text label;
    UNTIMED when none can be read."""
    if not label:
        return UNTIMED
    # "2-4 PM": the range start borrows the meridiem that follows - checked
    # first, or the generic search would read "4 PM".
    r = _RANGE.match(label)
    if r:
        h, mm, ap = int(r.group(1)), int(r.group(2) or 0), r.group(3).lower()
        if 1 <= h <= 12 and mm <= 59:
            return _h12(h, mm, ap)
    m = _CLOCK.search(label)
    if m:
        h, mm, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
        return _h12(h, mm, ap) if (1 <= h <= 12 and mm <= 59) else UNTIMED
    m = _CLOCK_24.search(label)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return UNTIMED
