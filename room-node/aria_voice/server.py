"""Aria low-cost voice, room-node half: local turn detection for the room page's cascade transport
(docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md). Holds no provider key; listens on localhost only and calls nothing.
Speech output is not here: the page plays the session's selected voice from the backend (routes/aria_voice.py).

WebSocket ws://127.0.0.1:8794 - one client is one call:
  in   binary                       mic PCM16 mono 16 kHz (the page's echo-cancelled microphone)
  in   {"type":"config", "silence_ms", "threshold"}   turn detection, from the room session's own settings
  out  {"type":"ready"}
  out  {"type":"speech_started"} / {"type":"speech_stopped", "wav": base64 16 kHz WAV of the utterance,
                                                       "early_ok": the speech_paused transcript is the whole turn}
  out  {"type":"speech_paused", "wav"}   speech went quiet for PAUSE_MS inside a turn: the page may transcribe
                                         early; {"type":"speech_resumed"} if the speaker carries on
"""
import asyncio
import base64
import collections
import io
import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("ARIA_VOICE_MODELS", os.path.join(HERE, "model"))   # silero_vad.onnx (installed by ctl.sh)
PORT = int(os.environ.get("ARIA_VOICE_PORT", "8794"))
MIC_RATE = 16000
PAUSE_MS = int(os.environ.get("ARIA_VOICE_PAUSE_MS", "400"))   # early-transcription point (turn end stays silence_ms)
WIN_MS = 512 * 1000 // MIC_RATE
PREROLL_WINDOWS = 600 // WIN_MS            # the VAD confirms speech ~0.25 s in: keep what came just before
PEAK_DECAY = 0.5 ** (WIN_MS / 500)


def wav_bytes(samples_i16: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(samples_i16.tobytes())
    return buf.getvalue()


def make_vad(silence_ms=1000, threshold=0.5):
    import sherpa_onnx as so
    c = so.VadModelConfig()
    c.silero_vad.model = f"{MODELS}/silero_vad.onnx"
    c.silero_vad.threshold = threshold
    c.silero_vad.min_silence_duration = silence_ms / 1000
    c.silero_vad.min_speech_duration = 0.25
    c.silero_vad.max_speech_duration = 30            # the backend's per-segment bound
    c.sample_rate = MIC_RATE
    c.num_threads = 1
    return so.VoiceActivityDetector(c, buffer_size_in_seconds=60)


class Call:
    def __init__(self, ws):
        self.ws = ws
        self.vad, self.speaking = make_vad(), False
        self.pending = np.zeros(0, dtype=np.float32)
        self.utt, self.peak, self.quiet_ms, self.paused = [], 0.0, 0, False
        self.silence_ms, self.pause_len = 1000, 0
        self.preroll = collections.deque(maxlen=PREROLL_WINDOWS)

    async def send(self, obj):
        await self.ws.send(json.dumps(obj))

    def on_mic(self, data: bytes):
        x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768
        self.pending = np.concatenate([self.pending, x])
        n = len(self.pending) // 512 * 512          # silero window
        if not n:
            return []
        block, self.pending = self.pending[:n], self.pending[n:]
        self.vad.accept_waveform(block)
        out = []
        if self.vad.is_speech_detected() and not self.speaking:
            self.speaking = True; out.append({"type": "speech_started"})
            self.utt, self.peak, self.quiet_ms, self.paused = list(self.preroll), 0.0, 0, False
        if self.speaking:
            out += self._pause_watch(block)
        else:
            self.preroll.extend(block.reshape(-1, 512))
        while not self.vad.empty():
            seg = np.asarray(self.vad.front.samples, dtype=np.float32); self.vad.pop()
            # The VAD's segment starts where it confirmed speech, cutting the first word ("turn off the overhead
            # light" -> "Overhead light.", Room 214 2026-10-17). The turn as heard - pre-roll included - is sent.
            if self.speaking and self.utt:
                seg = np.concatenate(self.utt)
            # The early transcript (taken at the pause) is the whole turn only if nothing was said after it: the
            # turn then ended one silence after the pause. Speech after it - even speech quieter than the pause
            # rule counts as sound - makes the turn longer, and the full turn must be transcribed instead.
            early_ok = bool(self.paused and (len(self.utt) - self.pause_len) * WIN_MS <= self.silence_ms + 300)
            self.speaking = False
            print(f"turn {len(seg) * 1000 // MIC_RATE} ms peak {self.peak:.3f} early_ok {early_ok}", flush=True)
            pcm = (np.clip(seg, -1, 1) * 32767).astype("<i2")
            out.append({"type": "speech_stopped", "early_ok": early_ok,
                        "wav": base64.b64encode(wav_bytes(pcm, MIC_RATE)).decode()})
        return out

    def _pause_watch(self, block):
        """Energy-based early pause inside a VAD turn (the VAD itself only reports the turn's end)."""
        out = []
        for w in block.reshape(-1, 512):
            self.utt.append(w)
            rms = float(np.sqrt(np.mean(w * w)))
            # Recent loudness (halves in ~0.5 s): one cough or bump must not make normal speech count as quiet.
            self.peak = max(rms, self.peak * PEAK_DECAY)
            if rms < max(0.004, 0.15 * self.peak):
                self.quiet_ms += WIN_MS
            else:
                if self.paused:
                    out.append({"type": "speech_resumed"})
                self.quiet_ms, self.paused = 0, False
            if not self.paused and self.quiet_ms >= PAUSE_MS and len(self.utt) * WIN_MS > 300 + PAUSE_MS:
                self.paused, self.pause_len = True, len(self.utt)
                pcm = (np.clip(np.concatenate(self.utt), -1, 1) * 32767).astype("<i2")
                out.append({"type": "speech_paused", "wav": base64.b64encode(wav_bytes(pcm, MIC_RATE)).decode()})
        return out

    async def handle(self, msg):
        if isinstance(msg, bytes):
            for ev in self.on_mic(msg):
                await self.send(ev)
            return
        m = json.loads(msg)
        if m.get("type") == "config":
            self.silence_ms = int(m.get("silence_ms") or 1000)
            self.vad = make_vad(self.silence_ms, float(m.get("threshold") or 0.5))



async def main():
    import websockets

    async def serve(ws):
        call = Call(ws)
        await call.send({"type": "ready"})
        async for msg in ws:
            await call.handle(msg)

    async with websockets.serve(serve, "127.0.0.1", PORT, max_size=2 ** 22):
        print(f"aria_voice listening on 127.0.0.1:{PORT}", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
