"""Tests for the room-node voice service. Pure tests always run; the live tests use the local models and a
recorded room clip, and are skipped where those are not installed. Nothing here touches the network.

Run: ../aria_wake/.venv/bin/python -m pytest test_server.py   (or any venv with sherpa-onnx + websockets)
"""
import base64
import json
import io
import os
import time
import wave

import numpy as np
import pytest

import server

CLIP = os.path.expanduser("~/aria-local-lab/audio/human_like/us_f_kristin_p04_room.wav")
HAVE_MODELS = os.path.exists(f"{server.MODELS}/silero_vad.onnx") and os.path.exists(CLIP)




def test_wav_round_trip():
    pcm = (np.sin(np.arange(1600) / 5) * 1000).astype("<i2")
    with wave.open(io.BytesIO(server.wav_bytes(pcm, 16000))) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (16000, 1, 1600)


def read_clip():
    with wave.open(CLIP) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        rate = w.getframerate()
    if rate != 16000:
        x = np.interp(np.arange(0, len(x), rate / 16000), np.arange(len(x)), x).astype("<i2")
    return x


class FakeWs:
    def __init__(self):
        self.out = []

    async def send(self, m):
        self.out.append((time.monotonic(), m))


@pytest.mark.skipif(not HAVE_MODELS, reason="local speech models / clip not installed")
def test_vad_finds_one_utterance_in_a_room_clip():
    call = server.Call(FakeWs())
    x = np.concatenate([np.zeros(8000, "<i2"), read_clip(), np.zeros(32000, "<i2")])   # 2 s trailing silence
    events = []
    for i in range(0, len(x), 1600):
        events += call.on_mic(x[i:i + 1600].tobytes())
    kinds = [e["type"] for e in events]
    assert kinds[0] == "speech_started" and "speech_stopped" in kinds
    # the early pause comes before the turn's end, so transcription can start sooner
    assert "speech_paused" in kinds and kinds.index("speech_paused") < kinds.index("speech_stopped")
    # the early-pause audio starts before the VAD confirmed speech, so no opening syllable is lost
    early = next(e for e in events if e["type"] == "speech_paused")
    with wave.open(io.BytesIO(base64.b64decode(early["wav"]))) as w:
        assert w.getnframes() >= 16000 * 2.6     # 2.38 s of speech + 0.4 s pause; without pre-roll it was 2.27 s
    seg = next(e for e in events if e["type"] == "speech_stopped")
    with wave.open(io.BytesIO(base64.b64decode(seg["wav"]))) as w:
        assert w.getnframes() / 16000 > 1.0


# --- Diag: numbers-only detector diagnostics (Room 214 measurement; the page opts in) ---

class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def tone(seconds, amp=0.3):
    return (np.sin(np.arange(int(16000 * seconds)) * 2 * np.pi * 440 / 16000) * amp).astype(np.float32)


def feed(diag, clock, x, vad_speech=False, block=2048, started_at=None):
    out = []
    for i in range(0, len(x), block):
        clock.t += block / 16000
        out += diag.feed(x[i:i + block], vad_speech, started_at == i)
    return out


def segments(out):
    return [m["data"] for m in out if m["data"]["kind"] == "energy_segment"]


def test_energy_without_detected_speech_is_reported_numbers_only():
    clock = Clock(); d = server.Diag(clock=clock, wall=lambda: 1000.0)
    out = feed(d, clock, np.concatenate([np.full(16000, 1e-4, np.float32), tone(1.5), np.zeros(16000, np.float32)]))
    [s] = segments(out)
    assert s["no_speech_detected"] is True and s["vad_speech_frames"] == 0 and s["vad_turn_started"] is False
    assert s["peak_dbfs"] > -15 and 1.4 <= s["duration_s"] <= 2.2 and s["start_epoch_ms"] >= 1000_000
    assert all(isinstance(v, (int, float, bool, str)) for v in s.values()) and set(s) == {
        "kind", "start_epoch_ms", "duration_s", "speech_frames", "peak_dbfs", "mean_dbfs", "noise_floor_dbfs",
        "clipped_frames", "vad_speech_frames", "vad_turn_started", "no_speech_detected"}


def test_energy_the_vad_flagged_is_not_reported_as_missed():
    clock = Clock(); d = server.Diag(clock=clock)
    x = np.concatenate([np.full(16000, 1e-4, np.float32), tone(1.5), np.zeros(16000, np.float32)])
    [s] = segments(feed(d, clock, x, vad_speech=True, started_at=16384))
    assert s["no_speech_detected"] is False and s["vad_speech_frames"] > 5 and s["vad_turn_started"] is True


def test_missing_frames_show_as_gaps_in_the_continuity_summary():
    clock = Clock(); d = server.Diag(clock=clock)
    feed(d, clock, np.zeros(16000 * 10, np.float32))
    clock.t += 1.5                                  # 1.5 s with no audio arriving from the page
    out = feed(d, clock, np.zeros(16000 * 25, np.float32))
    [c] = [m["data"] for m in out if m["data"]["kind"] == "continuity"]
    assert c["gaps_over_300ms"] == 1 and c["max_gap_ms"] >= 1500 and c["wall_s"] - c["audio_s"] > 1.3


def test_diag_is_rate_limited_and_counts_what_it_dropped():
    clock = Clock(); d = server.Diag(clock=clock)
    burst = np.concatenate([tone(0.4), np.zeros(9600, np.float32)])
    out = feed(d, clock, np.concatenate([np.full(16000, 1e-4, np.float32)] + [burst] * 40))
    assert len(out) == server.DIAG_MAX_PER_MIN                     # segments plus the continuity summary
    assert d.dropped == 40 - len(segments(out)) > 0


def test_diag_is_off_unless_the_page_asks_and_its_failure_never_stops_turn_detection():
    call = server.Call(FakeWs())
    assert call.diag is None
    asyncio_run(call.handle(json.dumps({"type": "config", "silence_ms": 1000, "threshold": 0.5})))
    assert call.diag is None
    asyncio_run(call.handle(json.dumps({"type": "config", "diagnostics": True})))
    assert isinstance(call.diag, server.Diag)

    class Boom:
        def feed(self, *a):
            raise ValueError("x")

    class Vad:                                     # stands in for Silero: speech in this block
        def accept_waveform(self, b): pass
        def is_speech_detected(self): return True
        def empty(self): return True

    call.vad, call.diag = Vad(), Boom()
    out = call.on_mic((np.ones(2048) * 1000).astype("<i2").tobytes())
    assert out[0] == {"type": "speech_started"}
    assert out[-1] == {"type": "diag", "data": {"kind": "diag_failed", "error": "ValueError"}} and call.diag is None
    assert all(m["type"] != "diag" for m in call.on_mic((np.ones(2048) * 1000).astype("<i2").tobytes()))


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


@pytest.mark.skipif(not HAVE_MODELS, reason="local speech models / clip not installed")
def test_early_ok_only_when_nothing_was_said_after_the_pause():
    clip = read_clip()

    def run(x):
        call = server.Call(FakeWs())
        events = []
        for i in range(0, len(x), 2048):
            events += call.on_mic(x[i:i + 2048].tobytes())
        return events

    lead, tail = np.zeros(8000, "<i2"), np.zeros(32000, "<i2")
    alone = [e for e in run(np.concatenate([lead, clip, tail])) if e["type"] == "speech_stopped"]
    assert alone and alone[-1]["early_ok"] is True            # the turn ended at its pause: reuse that transcript
    # A pause, then more words quieter than the pause rule counts as sound: the VAD keeps one turn going.
    quieter = (clip * 0.12).astype("<i2")
    events = run(np.concatenate([lead, clip, np.zeros(9600, "<i2"), quieter, tail]))
    stops = [e for e in events if e["type"] == "speech_stopped"]
    assert len(stops) == 1 and stops[0]["early_ok"] is False  # words after the pause: transcribe the whole turn
