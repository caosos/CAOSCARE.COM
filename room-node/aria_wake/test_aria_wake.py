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


def _chunks(level, n):
    rng = np.random.default_rng(1)
    return [(rng.standard_normal(1600) * level).astype(np.float32) for _ in range(n)]


def test_level_tracker_emits_one_summary_per_speech_segment_and_no_audio():
    import levels
    lt = levels.LevelTracker(gain_db=6.0)
    out = []
    for c in _chunks(0.001, 20) + _chunks(0.1, 6) + _chunks(0.001, 10) + _chunks(0.05, 4) + _chunks(0.001, 10):
        seg = lt.update(c)
        if seg:
            out.append(seg)
    assert len(out) == 2                                  # two segments, not one line per 100 ms frame
    first, second = out
    assert first["speech_frames"] == 6 and first["gain_db"] == 6.0 and first["mode"] == "listening"
    assert -22 < first["peak_dbfs"] < -8 and first["noise_floor_dbfs"] < -50
    assert second["peak_dbfs"] < first["peak_dbfs"]
    assert set(first) == {"duration_s", "speech_frames", "peak_dbfs", "mean_dbfs", "noise_floor_dbfs",
                          "clipped_frames", "gain_db", "detections", "detection_suppressed", "mode"}  # numbers only


def test_level_tracker_ignores_clicks_counts_detections_and_slices_long_sounds():
    import levels
    lt = levels.LevelTracker()
    segs = [lt.update(c) for c in _chunks(0.001, 20) + _chunks(0.2, 1) + _chunks(0.001, 10)]
    assert not any(segs)                                  # one 0.1 s click is not speech
    lt = levels.LevelTracker()
    for c in _chunks(0.001, 20) + _chunks(0.1, 3):
        lt.update(c)
    lt.note_detection(suppressed=True)
    got = [s for s in (lt.update(c, "conversation") for c in _chunks(0.001, 8)) if s]
    assert got[0]["detections"] == 1 and got[0]["detection_suppressed"] is True
    lt = levels.LevelTracker()
    longs = [s for s in (lt.update(c) for c in _chunks(0.001, 20) + _chunks(0.1, 700)) if s]
    assert len(longs) >= 2 and all(s["duration_s"] <= levels.MAX_SEGMENT_S + 0.2 for s in longs)


def test_apply_gain_boosts_and_clips_and_default_is_untouched():
    import detector
    x = np.array([0.1, -0.2, 0.9, -0.9], dtype=np.float32)
    assert detector.apply_gain(x, 0.0) is x
    y = detector.apply_gain(x, 6.0)
    assert np.allclose(y[:2], x[:2] * 1.9953, atol=1e-3)
    assert y.max() == 1.0 and y.min() == -1.0 and y.dtype == np.float32     # clipped, never past full scale
    assert np.allclose(detector.apply_gain(x, -6.0), x * 0.5012, atol=1e-3)


def test_gain_reaches_the_stream_detector_but_not_the_level_numbers():
    import detector
    seen = []

    class FakeSpotter:
        def create_stream(self): return object()
        def accept(self, s): seen.append(s)
    import types
    sp = FakeSpotter()
    sp.is_ready = lambda st: False
    sp.reset_stream = lambda st: None
    sd = detector.StreamDetector(sp, gain_db=10.0)
    sd.stream = types.SimpleNamespace(accept_waveform=lambda sr, s: seen.append(s))
    sd.feed(np.full(1600, 0.1, dtype=np.float32))
    assert abs(float(seen[0][0]) - 0.3162) < 1e-3          # the detector heard the boosted samples
    assert aw.GAIN_DB == 0.0                                # the live default is unchanged


def test_wake_stats_levels_split_detected_vs_missed_and_attach_misses():
    import wake_stats as ws
    t = lambda sec: f"2026-10-08T21:00:{sec:02d}+00:00"
    seg = lambda sec, peak, det, mode="listening": {"at": t(sec), "event": "audio_level", "duration_s": 1.2, "speech_frames": 10,
        "peak_dbfs": peak, "mean_dbfs": peak - 8, "noise_floor_dbfs": -62.0, "gain_db": 0.0, "detections": det,
        "mode": mode, "clipped_frames": 0}
    ev = [seg(5, -18.0, 1), seg(20, -41.0, 0), seg(30, -39.0, 0), seg(50, -15.0, 0, "conversation")]
    s = ws.summarize(ev, [{"at": t(33), "kind": "miss", "note": "said it 3x"}])
    lv = s["levels"]
    assert (lv["segments"], lv["listening"], lv["detected"], lv["undetected"]) == (4, 3, 1, 2)
    assert lv["peak_detected_p10_p50_p90"][1] == -18.0
    assert lv["peak_undetected_p10_p50_p90"][1] in (-41.0, -39.0)
    near = lv["misses"][0]["segments_before"]
    assert [g["peak_dbfs"] for g in near] == [-41.0, -39.0] and not any(g["detected"] for g in near)
    out = ws.render(s)
    assert "audio levels" in out and "miss mark" in out and "peak -39.0" in out
    assert "no audio_level events" in ws.render(ws.summarize([], []))
