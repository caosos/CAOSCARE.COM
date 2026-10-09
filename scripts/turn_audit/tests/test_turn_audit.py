import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from turn_audit import analyze

B = "2026-10-09T21:01:"   # times below are seconds after 21:01:00 UTC, the 2026-10-09 Room 214 session


def ev(sec, kind):
    return {"created_at": f"{B}{sec:09.6f}+00:00", "event_type": kind}


def lv(sec, dur, mean):
    return {"at": f"{B}{sec:09.6f}+00:00", "duration_s": dur, "mean_dbfs": mean}


EVENTS = [ev(13.06, "speech_started"), ev(15.58, "speech_stopped"), ev(16.06, "output_audio_buffer_started"),
          ev(21.53, "speech_started"), ev(21.53, "output_audio_buffer_stopped"), ev(30.05, "speech_stopped")]
LEVELS = [lv(15.01, 2.2, -25.4), lv(17.63, 2.5, -27.6), lv(20.11, 1.8, -32.3), lv(22.61, 1.8, -31.2), lv(29.31, 6.5, -28.1)]


def test_server_turn_end_matches_raw_capture():
    r = analyze(EVENTS, LEVELS, hold_ms=1000)
    first = r["turns"][0]
    assert abs(first["end_delta_s"]) < 0.3        # server and raw mic agree where the speech ended
    assert first["raw_peak_mean_dbfs"] > -35      # capture is not quiet


def test_raw_speech_that_resumed_before_the_server_committed_is_reported():
    # raw mic speech restarts 0.45 s before the server's speech_stopped, which is
    # before the assistant's first audio: it cannot be the speaker's echo
    r = analyze(EVENTS, LEVELS, hold_ms=1000)
    assert r["turns"][0]["raw_speech_resumed_s_before_commit"] == [0.45]


def test_raw_speech_after_the_commit_during_playback_is_ambiguous_not_called_a_miss():
    r = analyze(EVENTS, LEVELS, hold_ms=1000)
    assert {u["where"] for u in r["raw_speech_unseen_by_server"]} == {"during_assistant_playback"}


def test_clipped_turn_is_detected():
    # server ends 1.2 s before the raw mic stops: syllables lost
    r = analyze([ev(5, "speech_started"), ev(7, "speech_stopped")], [lv(9.0, 4.0, -30)], hold_ms=1000)
    assert r["turns"][0]["end_delta_s"] < -1.0


def test_idle_speech_unseen_is_a_real_miss():
    r = analyze([ev(5, "speech_started"), ev(7, "speech_stopped"), ev(14, "response_created")], [lv(6.5, 2.0, -30), lv(12, 2.0, -30)], hold_ms=1000)
    assert r["raw_speech_unseen_by_server"][0]["where"] == "while_idle"
