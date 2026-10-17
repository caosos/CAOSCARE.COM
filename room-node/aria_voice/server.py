"""Aria low-cost voice, room-node half: local VAD + local TTS for the room page's cascade transport
(docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md). Holds no provider key; listens on localhost only and calls nothing.

WebSocket ws://127.0.0.1:8794 - one client is one call:
  in   binary                       mic PCM16 mono 16 kHz (the page's echo-cancelled microphone)
  in   {"type":"config", "silence_ms", "threshold"}   turn detection, from the room session's own settings
  in   {"type":"speak", "id", "text"}                 queue one sentence (lexicon applied)
  in   {"type":"stop"}                                 drop current + queued speech now (barge-in)
  out  {"type":"ready", "sample_rate"}
  out  {"type":"speech_started"} / {"type":"speech_stopped", "wav": base64 16 kHz WAV of the utterance}
  out  binary                       Aria's audio: 4-byte little-endian generation + PCM16 mono at sample_rate
  out  {"type":"spoken", "id", "gen"}                  that sentence's audio has all been sent
  out  {"type":"stopped", "gen"}                       frames of an older generation must be dropped
"""
import asyncio
import base64
import io
import json
import os
import re
import struct
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("ARIA_VOICE_MODELS", os.path.expanduser("~/aria-local-lab/speech-models/sherpa"))
PORT = int(os.environ.get("ARIA_VOICE_PORT", "8794"))
TTS_THREADS = int(os.environ.get("ARIA_VOICE_TTS_THREADS", "4"))
MIC_RATE = 16000
CHUNK_S = 0.25                                  # TTS audio is sent in pieces this long


def load_lexicon(path=os.path.join(HERE, "lexicon.json")):
    with open(path) as f:
        lex = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    keys = sorted(lex, key=len, reverse=True)   # "CAOS Care" before "CAOS"
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b", re.IGNORECASE)
    by_lower = {k.lower(): v for k, v in lex.items()}
    return lambda text: pattern.sub(lambda m: by_lower[m.group(0).lower()], text)


def wav_bytes(samples_i16: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(samples_i16.tobytes())
    return buf.getvalue()


def make_tts():
    import sherpa_onnx as so
    d = f"{MODELS}/vits-piper-en_US-lessac-medium"
    m = so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(
        model=f"{d}/en_US-lessac-medium.onnx", tokens=f"{d}/tokens.txt", data_dir=f"{d}/espeak-ng-data"),
        num_threads=TTS_THREADS)
    return so.OfflineTts(so.OfflineTtsConfig(model=m, max_num_sentences=1))


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
    def __init__(self, ws, tts, say):
        self.ws, self.tts, self.say = ws, tts, say
        self.vad, self.speaking, self.gen = make_vad(), False, 0
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pending = np.zeros(0, dtype=np.float32)

    async def send(self, obj):
        await self.ws.send(json.dumps(obj))

    def on_mic(self, data: bytes):
        x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768
        self.pending = np.concatenate([self.pending, x])
        n = len(self.pending) // 512 * 512          # silero window
        if not n:
            return []
        self.vad.accept_waveform(self.pending[:n]); self.pending = self.pending[n:]
        out = []
        if self.vad.is_speech_detected() and not self.speaking:
            self.speaking = True; out.append({"type": "speech_started"})
        while not self.vad.empty():
            seg = np.asarray(self.vad.front.samples, dtype=np.float32); self.vad.pop()
            self.speaking = False
            pcm = (np.clip(seg, -1, 1) * 32767).astype("<i2")
            out.append({"type": "speech_stopped", "wav": base64.b64encode(wav_bytes(pcm, MIC_RATE)).decode()})
        return out

    async def speaker(self):
        """Synthesizes queued sentences one at a time, sending audio as it is produced."""
        loop = asyncio.get_running_loop()
        while True:
            sid, text, gen = await self.queue.get()
            if gen != self.gen:
                continue
            frames: asyncio.Queue = asyncio.Queue()

            def cb(samples, progress):              # sherpa calls this as audio is generated
                if gen != self.gen:
                    return 0                        # barge-in: stop generating
                loop.call_soon_threadsafe(frames.put_nowait, np.asarray(samples, dtype=np.float32).copy())
                return 1

            job = loop.run_in_executor(None, lambda: self.tts.generate(self.say(text), sid=0, speed=1.0, callback=cb))
            job.add_done_callback(lambda _: loop.call_soon_threadsafe(frames.put_nowait, None))
            rate, step = self.tts.sample_rate, int(self.tts.sample_rate * CHUNK_S)
            while (x := await frames.get()) is not None:
                if gen != self.gen:
                    continue
                pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
                for i in range(0, len(pcm), step):
                    await self.ws.send(struct.pack("<I", gen) + pcm[i:i + step].tobytes())
            if gen == self.gen:
                await self.send({"type": "spoken", "id": sid, "gen": gen})

    async def handle(self, msg):
        if isinstance(msg, bytes):
            for ev in self.on_mic(msg):
                await self.send(ev)
            return
        m = json.loads(msg)
        if m.get("type") == "config":
            self.vad = make_vad(int(m.get("silence_ms") or 1000), float(m.get("threshold") or 0.5))
        elif m.get("type") == "speak" and (m.get("text") or "").strip():
            await self.queue.put((m.get("id"), m["text"], self.gen))
        elif m.get("type") == "stop":
            self.gen += 1
            await self.send({"type": "stopped", "gen": self.gen})


async def main():
    import websockets
    tts, say = make_tts(), load_lexicon()
    tts.generate("Ready.", sid=0)                   # warm the model before the first call

    async def serve(ws):
        call = Call(ws, tts, say)
        await call.send({"type": "ready", "sample_rate": tts.sample_rate, "gen": call.gen})
        task = asyncio.create_task(call.speaker())
        try:
            async for msg in ws:
                await call.handle(msg)
        finally:
            task.cancel()

    async with websockets.serve(serve, "127.0.0.1", PORT, max_size=2 ** 22):
        print(f"aria_voice listening on 127.0.0.1:{PORT}", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
