"""Resident Aria core: CAOSCARE_CONTINUITY_RECENT_MINUTES lets Aria pick a thread back up when the last
session ended minutes ago; off by default (block identical to before). Pure render tests, no DB."""
import os, sys
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import now_utc  # noqa: E402
import routes.aria_continuity as c  # noqa: E402


def state(minutes_ago):
    t = (now_utc() - timedelta(minutes=minutes_ago)).isoformat()
    return {"has_continuity": True, "sessions": [{"session_id": "s1", "age_phrase": f"{minutes_ago} minutes ago", "ended_at": t,
            "end_reason": None, "unfinished": False, "clean_close": True, "turn_count": 2,
            "_rows": [{"role": "user", "content": "Tell me about the Cubs game", "created_at": t},
                      {"role": "assistant", "content": "Sure, which part?", "created_at": t}]}]}


def test_off_by_default_is_unchanged(monkeypatch):
    monkeypatch.delenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", raising=False)
    b = c.render_continuity_block(state(2), "Michael")
    assert "was talking with you only" not in b and "never re-file or reopen a request" in b


def test_recent_return_note_when_enabled(monkeypatch):
    monkeypatch.setenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", "10")
    b = c.render_continuity_block(state(2), "Michael")
    assert "Michael was talking with you only 2 minutes ago." in b and "never invent" in b
    assert "Tell me about the Cubs game" in b


def test_older_session_gets_no_note(monkeypatch):
    monkeypatch.setenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", "10")
    assert "was talking with you only" not in c.render_continuity_block(state(45), "Michael")


def test_bad_value_means_off(monkeypatch):
    monkeypatch.setenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", "soon")
    assert c._recent_minutes() == 0.0


def test_recent_return_may_notice_it_warmly_without_a_fixed_script(monkeypatch):
    monkeypatch.setenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", "10")
    b = c.render_continuity_block(state(1), "Michael")
    assert "didn't I just talk to you" in b and "not that exact line every time" in b


def test_next_day_session_is_still_known(monkeypatch):
    """da-a3817b6b9c: a conversation from yesterday evening is still in context the next afternoon."""
    monkeypatch.delenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", raising=False)
    assert c.CONTINUITY_WINDOW_HOURS >= 48
    st = state(20 * 60)
    st["sessions"][0]["age_phrase"] = "yesterday"
    b = c.render_continuity_block(st, "Michael")
    assert "### Yesterday" in b and "Tell me about the Cubs game" in b
    assert "was talking with you only" not in b          # not treated as the same conversation
    assert "brief question about something" in b


def test_age_phrase_uses_calendar_days_in_facility_time(monkeypatch):
    from zoneinfo import ZoneInfo
    from routes.aria_time import age_phrase
    from routes.realtime_facility import FACILITY_TZ
    tz = ZoneInfo(FACILITY_TZ)
    local_now = now_utc().astimezone(tz)
    yday_late = (local_now - timedelta(days=1)).replace(hour=23, minute=30, second=0, microsecond=0)
    if (local_now - yday_late).total_seconds() >= 6 * 3600:   # beyond the hours phrasing
        assert age_phrase(yday_late) == "yesterday"
    assert age_phrase(local_now - timedelta(days=3, hours=1)) in ("3 days ago", "4 days ago")


def test_each_prior_call_carries_its_clock_time(monkeypatch):
    monkeypatch.delenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", raising=False)
    b = c.render_continuity_block(state(6), "Michael")
    import re
    assert re.search(r"### 6 minutes ago \(\w+day \d{1,2}:\d{2} [AP]M\)", b), b
