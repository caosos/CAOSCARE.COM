"""Local "Aria" wake-word listener for a CAOSCare room endpoint.

A trigger, not a conversation participant (docs/ARIA_WAKE_WORD_ARCHITECTURE.md).
It reads the room's existing audio capture endpoint (the eMeet, via the
PulseAudio default source - a shared, non-exclusive tap), runs an on-device
keyword spotter, and tells the room page over a localhost-only WebSocket
that "Aria" was heard. The page then starts the existing Realtime session
through its normal path. Nothing here claims leases, mints sessions, calls
OpenAI, stores audio, or transcribes speech.

Engine: sherpa-onnx open-vocabulary keyword spotting (Apache-2.0) - chosen
because no usable pretrained openWakeWord "Aria" model exists yet and this
needs no training. It runs natively on Android too (sherpa-onnx's own KWS
AAR), so the protocol below is the portable part, not this Python file.

Protocol (JSON text frames, ws://127.0.0.1:<port>):
  server -> page  {"type":"hello", ...detector info}
                  {"type":"wake", "wake_id", "keyword", "detected_at", ...}
                  {"type":"listening", "at", "reason"}   (return-to-wake ack)
  page -> server  {"type":"state", "state":"conversation"|"listening", "reason"?}
While the page reports "conversation" (or a wake is pending), detections are
suppressed, so Aria's own voice can never re-trigger the wake word.
"""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

import numpy as np
import sherpa_onnx
import websockets

HOST = "127.0.0.1"  # never bind beyond this machine
PORT = int(os.environ.get("ARIA_WAKE_PORT", "8765"))
ORIGINS = [o.strip() for o in os.environ.get(
    "ARIA_WAKE_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
MODEL_DIR = os.environ.get("ARIA_WAKE_MODEL_DIR", os.path.join(os.path.dirname(__file__), "model"))
KEYWORDS_FILE = os.environ.get("ARIA_WAKE_KEYWORDS", os.path.join(os.path.dirname(__file__), "keywords.txt"))
KEYWORDS_SCORE = float(os.environ.get("ARIA_WAKE_KEYWORDS_SCORE", "1.0"))
KEYWORDS_THRESHOLD = float(os.environ.get("ARIA_WAKE_KEYWORDS_THRESHOLD", "0.15"))
SOURCE = os.environ.get("ARIA_WAKE_SOURCE", "")  # PulseAudio source; empty = system default
PENDING_WAKE_TIMEOUT_S = 20   # page never confirmed a conversation -> resume listening
RESUME_COOLDOWN_S = 1.5       # ignore the tail of Aria's last words after a session ends
SAMPLE_RATE = 16000
CHUNK = 1600                  # 100 ms


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(event, **fields):
    print(json.dumps({"at": now_iso(), "event": event, **fields}), flush=True)


def resolve_source():
    if SOURCE:
        return SOURCE
    out = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True)
    return out.stdout.strip() or "@DEFAULT_SOURCE@"


def build_spotter():
    m = MODEL_DIR
    return sherpa_onnx.KeywordSpotter(
        tokens=f"{m}/tokens.txt",
        encoder=f"{m}/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
        decoder=f"{m}/decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
        joiner=f"{m}/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
        keywords_file=KEYWORDS_FILE, num_threads=1, provider="cpu",
        keywords_score=KEYWORDS_SCORE, keywords_threshold=KEYWORDS_THRESHOLD,
    )


def spot(spotter, stream, samples):
    """Feed one chunk; return the keyword if it completed in this chunk."""
    stream.accept_waveform(SAMPLE_RATE, samples)
    while spotter.is_ready(stream):
        spotter.decode_stream(stream)
        kw = spotter.get_result(stream)
        if kw:
            spotter.reset_stream(stream)
            return kw
    return None


class SilenceReset:
    """Signals a spotter-stream reset after a pause that follows speech.

    Measured 2026-09-23 on synthetic "Aria" clips: one never-reset stream
    fed continuous room audio drifts (22/30 detected vs 26-27/30 when each
    utterance starts fresh), so the stream is cleared at natural pauses.
    Energy only - no speech content is kept or inspected."""

    QUIET_CHUNKS = 8  # 0.8 s of quiet after speech

    def __init__(self):
        self.floor = None
        self.heard_speech = False
        self.quiet = 0

    def update(self, samples):
        rms = float(np.sqrt(np.mean(samples * samples)) + 1e-9)
        self.floor = rms if self.floor is None or rms < self.floor else self.floor * 0.999 + rms * 0.001
        if rms > max(self.floor * 3.0, 0.003):
            self.heard_speech, self.quiet = True, 0
            return False
        self.quiet += 1
        if self.heard_speech and self.quiet >= self.QUIET_CHUNKS:
            self.heard_speech = False
            return True
        return False


class WakeState:
    """listening -> (wake) -> pending -> (page: conversation) -> conversation
    -> (page: listening) -> listening. Only `listening` may emit a wake."""

    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "listening"
        self.mode_since = time.monotonic()
        self.cooldown_until = 0.0
        self.reset_stream = False

    def set(self, mode, cooldown=0.0):
        with self.lock:
            self.mode, self.mode_since = mode, time.monotonic()
            self.cooldown_until = time.monotonic() + cooldown
            self.reset_stream = True

    def may_wake(self):
        with self.lock:
            if self.mode == "pending" and time.monotonic() - self.mode_since > PENDING_WAKE_TIMEOUT_S:
                self.mode, self.reset_stream = "listening", True
                log("pending_wake_expired")
            return self.mode == "listening" and time.monotonic() >= self.cooldown_until


class Server:
    def __init__(self, device):
        self.device = device
        self.clients = set()
        self.state = WakeState()
        self.loop = None

    def info(self):
        return {"detector": "sherpa-onnx-kws", "model": os.path.basename(os.path.abspath(MODEL_DIR)),
                "keywords_score": KEYWORDS_SCORE, "keywords_threshold": KEYWORDS_THRESHOLD,
                "audio_input_device": self.device, "sample_rate": SAMPLE_RATE}

    async def broadcast(self, msg):
        data = json.dumps(msg)
        for ws in list(self.clients):
            try:
                await ws.send(data)
            except Exception:
                self.clients.discard(ws)

    async def handler(self, ws):
        self.clients.add(ws)
        log("client_connected", clients=len(self.clients))
        await ws.send(json.dumps({"type": "hello", "mode": self.state.mode, **self.info()}))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get("type") != "state":
                    continue
                if msg.get("state") == "conversation":
                    self.state.set("conversation")
                    log("mode_conversation", reason=msg.get("reason"))
                elif msg.get("state") == "listening" and self.state.mode != "listening":
                    self.state.set("listening", cooldown=RESUME_COOLDOWN_S)
                    log("mode_listening", reason=msg.get("reason"))
                    await self.broadcast({"type": "listening", "at": now_iso(), "reason": msg.get("reason")})
        finally:
            self.clients.discard(ws)
            log("client_disconnected", clients=len(self.clients))

    def on_detect(self, keyword):
        """Called from the audio thread."""
        if not self.state.may_wake():
            log("detection_suppressed", keyword=keyword, mode=self.state.mode)
            return
        if not self.clients:
            log("detection_no_client", keyword=keyword)
            return
        self.state.set("pending")
        wake = {"type": "wake", "wake_id": f"wake_{uuid.uuid4().hex[:12]}", "keyword": keyword,
                "detected_at": now_iso(), "confidence": None,  # engine exposes no score; thresholded internally
                **self.info()}
        log("wake_detected", **{k: v for k, v in wake.items() if k != "type"})
        asyncio.run_coroutine_threadsafe(self.broadcast(wake), self.loop)

    def audio_loop(self):
        spotter = build_spotter()
        stream = spotter.create_stream()
        cmd = ["parec", "--raw", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1",
               "--latency-msec=100", f"--device={self.device}"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        log("capture_started", device=self.device, cmd=" ".join(cmd))
        nbytes = CHUNK * 2
        silence = SilenceReset()
        while True:
            buf = proc.stdout.read(nbytes)
            if not buf:
                log("capture_ended", returncode=proc.poll())
                os._exit(1)  # let the service manager restart us; never run deaf
            if self.state.reset_stream:
                self.state.reset_stream = False
                spotter.reset_stream(stream)
            samples = np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
            kw = spot(spotter, stream, samples)
            if kw:
                self.on_detect(kw)
            elif silence.update(samples):
                spotter.reset_stream(stream)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        threading.Thread(target=self.audio_loop, daemon=True).start()
        async with websockets.serve(self.handler, HOST, PORT, origins=ORIGINS):
            log("serving", host=HOST, port=PORT, origins=ORIGINS, **self.info())
            await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(Server(resolve_source()).run())
    except KeyboardInterrupt:
        sys.exit(0)
