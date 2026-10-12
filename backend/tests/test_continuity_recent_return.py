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
    assert "was talking with you only" not in b and "Do not reopen these topics" in b


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
