"""Synthetic speech for acoustic screening (OpenAI TTS, cached).

Every clip produced here is SYNTHETIC evidence. It never substitutes for
real speakers or physical Room 214 testing. Clips are cached by a hash of
(model, voice, instructions, text) so a run is reproducible without paying
for or re-requesting audio. Only the candidate/negative TEXT is sent to the
API - never room audio or resident data. Requires OPENAI_API_KEY.
"""
import hashlib
import io
import json
import os
import urllib.request
import wave

import numpy as np
from scipy.signal import resample_poly

from ..config import cache_dir

MODEL = "gpt-4o-mini-tts"
VOICES = ("alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse")
SAMPLE_RATE = 16000


def _cache_path(key):
    d = os.path.join(cache_dir(), "tts")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, hashlib.sha256(key.encode()).hexdigest()[:24] + ".wav")


def _request(text, voice, instructions):
    body = {"model": MODEL, "voice": voice, "input": text, "response_format": "wav"}
    if instructions:
        body["instructions"] = instructions
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _decode(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        sr, n = w.getframerate(), w.getnframes()
        pcm = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() > 1:
            pcm = pcm.reshape(-1, w.getnchannels()).mean(axis=1)
    if sr != SAMPLE_RATE:
        g = np.gcd(sr, SAMPLE_RATE)
        pcm = resample_poly(pcm, SAMPLE_RATE // g, sr // g).astype(np.float32)
    return pcm


def synth(text, voice, instructions=""):
    """16 kHz mono float32 audio for text in a voice/style (cached)."""
    path = _cache_path("|".join((MODEL, voice, instructions, text)))
    if not os.path.exists(path):
        data = _request(text, voice, instructions)
        # OpenAI's streaming WAV header can carry a placeholder length; re-wrap cleanly.
        pcm = _decode_lenient(data)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    with open(path, "rb") as fh:
        return _decode(fh.read())


def _decode_lenient(data):
    """PCM16 24 kHz samples from a WAV whose size fields may be unreliable."""
    idx = data.find(b"data")
    raw = data[idx + 8:] if idx >= 0 else data[44:]
    raw = raw[: len(raw) // 2 * 2]
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
