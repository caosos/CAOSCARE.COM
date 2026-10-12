"""marin/cedar are allowed (provider Realtime guide, 2026-10-12); the default voice is unchanged."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routes import realtime  # noqa: E402


def test_new_voices_allowed_default_unchanged():
    assert {"marin", "cedar"} <= realtime.ALLOWED_VOICES
    assert realtime.DEFAULT_VOICE == "shimmer"


def test_forced_voice_setting(monkeypatch):
    monkeypatch.delenv("CAOSCARE_REALTIME_VOICE", raising=False)
    assert realtime.session_voice("shimmer") == "shimmer" and realtime.session_voice(None) == "shimmer"
    assert realtime.session_voice("bogus") == "shimmer"
    monkeypatch.setenv("CAOSCARE_REALTIME_VOICE", "marin")
    assert realtime.session_voice("shimmer") == "marin" and realtime.session_voice(None) == "marin"
    monkeypatch.setenv("CAOSCARE_REALTIME_VOICE", "not-a-voice")
    assert realtime.session_voice("ash") == "ash"
