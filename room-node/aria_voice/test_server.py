"""Tests for the room-node voice service. Pure tests always run; the live tests use the local models and a
recorded room clip, and are skipped where those are not installed. Nothing here touches the network.

Run: ../aria_wake/.venv/bin/python -m pytest test_server.py   (or any venv with sherpa-onnx + websockets)
"""
import base64
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
    seg = next(e for e in events if e["type"] == "speech_stopped")
    with wave.open(io.BytesIO(base64.b64decode(seg["wav"]))) as w:
        assert w.getnframes() / 16000 > 1.0
