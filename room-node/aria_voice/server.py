"""Aria low-cost voice, room-node half: local turn detection for the room page's cascade transport
(docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md). Holds no provider key; listens on localhost only and calls nothing.
Speech output is not here: the page plays the session's selected voice from the backend (routes/aria_voice.py).

WebSocket ws://127.0.0.1:8794 - one client is one call:
  in   binary                       mic PCM16 mono 16 kHz (the page's echo-cancelled microphone)
  in   {"type":"config", "silence_ms", "threshold"}   turn detection, from the room session's own settings
  out  {"type":"ready"}
  out  {"type":"speech_started"} / {"type":"speech_stopped", "wav": base64 16 kHz WAV of the utterance}
  out  {"type":"speech_paused", "wav"}   speech went quiet for PAUSE_MS inside a turn: the page may transcribe
                                         early; {"type":"speech_resumed"} if the speaker carries on
"""
import asyncio
import base64
import io
import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("ARIA_VOICE_MODELS", os.path.expanduser("~/aria-local-lab/speech-models/sherpa"))
PORT = int(os.environ.get("ARIA_VOICE_PORT", "8794"))
MIC_RATE = 16000
PAUSE_MS = int(os.environ.get("ARIA_VOICE_PAUSE_MS", "400"))   # early-transcription point (turn end stays silence_ms)
WIN_MS = 512 * 1000 // MIC_RATE


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
            self.utt, self.peak, self.quiet_ms, self.paused = [], 0.0, 0, False
        if self.speaking:
            out += self._pause_watch(block)
        while not self.vad.empty():
            seg = np.asarray(self.vad.front.samples, dtype=np.float32); self.vad.pop()
            self.speaking = False
            pcm = (np.clip(seg, -1, 1) * 32767).astype("<i2")
            out.append({"type": "speech_stopped", "wav": base64.b64encode(wav_bytes(pcm, MIC_RATE)).decode()})
        return out

    def _pause_watch(self, block):
        """Energy-based early pause inside a VAD turn (the VAD itself only reports the turn's end)."""
        out = []
        for w in block.reshape(-1, 512):
            self.utt.append(w)
            rms = float(np.sqrt(np.mean(w * w)))
            self.peak = max(self.peak, rms)
            if rms < max(0.004, 0.15 * self.peak):
                self.quiet_ms += WIN_MS
            else:
                if self.paused:
                    out.append({"type": "speech_resumed"})
                self.quiet_ms, self.paused = 0, False
            if not self.paused and self.quiet_ms >= PAUSE_MS and len(self.utt) * WIN_MS > 300 + PAUSE_MS:
                self.paused = True
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
            self.vad = make_vad(int(m.get("silence_ms") or 1000), float(m.get("threshold") or 0.5))



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
