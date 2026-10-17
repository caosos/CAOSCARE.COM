"""Tests for the room-node voice service. Pure tests always run; the live tests use the local models and a
recorded room clip, and are skipped where those are not installed. Nothing here touches the network.

Run: ../aria_wake/.venv/bin/python -m pytest test_server.py   (or any venv with sherpa-onnx + websockets)
"""
import asyncio
import base64
import io
import json
import os
import struct
import time
import wave

import numpy as np
import pytest

import server

CLIP = os.path.expanduser("~/aria-local-lab/audio/human_like/us_f_kristin_p04_room.wav")
HAVE_MODELS = os.path.exists(f"{server.MODELS}/vits-piper-en_US-lessac-medium") and os.path.exists(CLIP)


def test_lexicon_says_kay_oss_care():
    say = server.load_lexicon()
    assert say("Welcome to CAOSCare.") == "Welcome to Kay-oss Care."
    assert say("CAOS Care staff and caos care nurses") == "Kay-oss Care staff and Kay-oss Care nurses"
    assert say("CAOS runs here; chaos does not change.") == "Kay-oss runs here; chaos does not change."


def test_lexicon_says_ah_ree_uh_not_area():
    say = server.load_lexicon()
    assert say("Hi Michael, it's Aria.") == "Hi Michael, it's Ah-ree-uh."
    assert say("Ask ARIA or aria") == "Ask Ah-ree-uh or Ah-ree-uh"
    assert say("the Arian area") == "the Arian area"          # whole words only


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
    call = server.Call(FakeWs(), None, str)
    x = np.concatenate([np.zeros(8000, "<i2"), read_clip(), np.zeros(32000, "<i2")])   # 2 s trailing silence
    events = []
    for i in range(0, len(x), 1600):
        events += call.on_mic(x[i:i + 1600].tobytes())
    kinds = [e["type"] for e in events]
    assert kinds[0] == "speech_started" and "speech_stopped" in kinds
    seg = next(e for e in events if e["type"] == "speech_stopped")
    with wave.open(io.BytesIO(base64.b64decode(seg["wav"]))) as w:
        assert w.getnframes() / 16000 > 1.0


@pytest.mark.skipif(not HAVE_MODELS, reason="local speech models not installed")
def test_first_audio_is_fast_and_stop_drops_the_rest():
    async def go():
        ws = FakeWs()
        call = server.Call(ws, server.make_tts(), server.load_lexicon())
        task = asyncio.create_task(call.speaker())
        t0 = time.monotonic()
        await call.handle(json.dumps({"type": "speak", "id": "s1", "text": "Hi Michael, it's Aria."}))
        await call.handle(json.dumps({"type": "speak", "id": "s2",
                                      "text": "This is a much longer sentence that I will be interrupted in the middle of, "
                                              "so none of its later audio should ever be sent to the room speaker."}))
        while not any(isinstance(m, bytes) for _, m in ws.out):
            await asyncio.sleep(0.01)
        first = next(t for t, m in ws.out if isinstance(m, bytes)) - t0
        while not any(isinstance(m, str) and json.loads(m).get("id") == "s1" for _, m in ws.out):
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.2)
        await call.handle(json.dumps({"type": "stop"}))
        stop_at = len(ws.out)
        await asyncio.sleep(1.5)
        task.cancel()
        return first, ws.out, stop_at
    first, out, stop_at = asyncio.run(go())
    assert first < 0.6, f"first audio after {first:.2f}s"
    late = [m for _, m in out[stop_at:] if isinstance(m, bytes) and struct.unpack("<I", m[:4])[0] == 0]
    assert late == [], f"{len(late)} frames of interrupted speech sent after stop"
    assert not any(isinstance(m, str) and json.loads(m).get("id") == "s2" for _, m in out)
