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


def test_endpoint_is_off_unless_explicitly_enabled():
    assert not aw.endpoint_enabled({})
    assert not aw.endpoint_enabled({aw.ENABLE_ENV: "0"})
    assert not aw.endpoint_enabled({aw.ENABLE_ENV: "true"})
    assert aw.endpoint_enabled({aw.ENABLE_ENV: "1"})
    assert aw.endpoint_enabled({aw.ENABLE_ENV_ALIAS: "1"})     # earlier name still honoured


def test_default_phrase_is_hey_aria_and_single_word_is_refused():
    labels = aw.keyword_labels(aw.DEFAULT_KEYWORDS)
    assert labels == ["HEY_ARIA"]
    assert aw.phrase_text(labels) == "Hey Aria"
    assert aw.phrase_problem(labels, {}) is None
    single = aw.keyword_labels(aw.DEFAULT_KEYWORDS.replace("keywords.txt", "keywords_aria_single_word.txt"))
    assert aw.phrase_problem(single, {}) is not None
    assert aw.phrase_problem(single, {aw.SINGLE_WORD_ENV: "1"}) is None   # comparison testing only
    assert aw.phrase_problem([], {}) is not None


def test_refuses_to_start_with_single_word_keywords(tmp_path):
    import os, subprocess, sys
    env = dict(os.environ, ARIA_WAKE_ENABLE="1",
               ARIA_WAKE_KEYWORDS=os.path.join(os.path.dirname(aw.__file__), "keywords_aria_single_word.txt"))
    env.pop("ARIA_WAKE_ALLOW_SINGLE_WORD", None)
    r = subprocess.run([sys.executable, aw.__file__], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2
    assert "single-word" in r.stderr
    assert "refused_to_start" in r.stdout


def test_wake_stats_tallies_log_and_marks(tmp_path):
    import json as _j
    import wake_stats as ws
    t = lambda sec: f"2026-10-08T20:00:{sec:02d}+00:00"
    ev = [
        {"at": t(0), "event": "wake_detected", "phrase": "Hey Aria"},
        {"at": t(1), "event": "mode_conversation"},
        {"at": t(5), "event": "detection_suppressed", "mode": "conversation"},
        {"at": t(20), "event": "mode_listening"},
        {"at": t(30), "event": "wake_detected", "phrase": "Hey Aria"},
        {"at": t(50), "event": "pending_wake_expired"},
        {"at": t(55), "event": "detection_no_client"},
    ]
    marks = [{"at": t(32), "kind": "false"}, {"at": t(40), "kind": "miss"}]
    s = ws.summarize(ev, marks)
    assert (s["wakes"], s["confirmed"], s["unconfirmed"], s["no_client"], s["suppressed"]) == (2, 1, 1, 1, 1)
    assert s["confirm_latency_s"] == [1.0] and s["session_s"] == [19.0]
    assert s["marks"]["false"] == 1 and s["marks"]["false_matched_to_wake"] == 1 and s["marks"]["miss"] == 1
    assert "Hey Aria" in ws.render(s)
    f = tmp_path / "m.jsonl"
    ws.main(["mark", "miss", "--note", "x", "--marks", str(f)])
    assert _j.loads(f.read_text())["kind"] == "miss"
