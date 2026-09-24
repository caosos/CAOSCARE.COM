"""State-machine tests for the wake listener (no audio device or model needed).

Run: .venv/bin/python -m pytest test_aria_wake.py
"""
import time

import numpy as np

import aria_wake as aw


def test_only_listening_mode_may_wake():
    s = aw.WakeState()
    assert s.may_wake()
    s.set("pending")
    assert not s.may_wake()
    s.set("conversation")
    assert not s.may_wake()


def test_resume_cooldown_blocks_tail_of_arias_speech():
    s = aw.WakeState()
    s.set("listening", cooldown=0.2)
    assert not s.may_wake()
    time.sleep(0.25)
    assert s.may_wake()


def test_unconfirmed_wake_expires_back_to_listening(monkeypatch):
    s = aw.WakeState()
    s.set("pending")
    monkeypatch.setattr(aw, "PENDING_WAKE_TIMEOUT_S", 0)
    time.sleep(0.01)
    assert s.may_wake()
    assert s.mode == "listening"


def test_silence_reset_fires_once_after_speech_then_pause():
    r = aw.SilenceReset()
    quiet = np.full(1600, 0.0005, dtype=np.float32)
    loud = np.full(1600, 0.1, dtype=np.float32)
    assert not any(r.update(quiet) for _ in range(20))       # silence alone never resets
    assert not r.update(loud)
    fired = [r.update(quiet) for _ in range(aw.SilenceReset.QUIET_CHUNKS + 5)]
    assert fired.count(True) == 1
    assert fired.index(True) == aw.SilenceReset.QUIET_CHUNKS - 1
