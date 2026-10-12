"""marin/cedar are allowed (provider Realtime guide, 2026-10-12); the default voice is unchanged."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routes import realtime  # noqa: E402


def test_new_voices_allowed_default_unchanged():
    assert {"marin", "cedar"} <= realtime.ALLOWED_VOICES
    assert realtime.DEFAULT_VOICE == "shimmer"
