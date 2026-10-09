"""Local "Hey Aria" wake-word listener - EliteDesk home endpoint.

An ADDITIONAL Aria voice endpoint on the EliteDesk, speaking the same
detector->page protocol the Home Assistant Voice PE endpoint will use. Not
standard apartment hardware: the standard apartment design (Michael,
2026-10-03) is one central EliteDesk server with a Voice PE per apartment
(docs/ROOM_AUDIO_ARCHITECTURE.md). Disabled by default: it only starts with
ARIA_WAKE_ENABLE=1 (alias ARIA_WAKE_ENABLE_LEGACY=1). It may only be
considered for removal after Voice PE real-room acceptance proves wake
accuracy, conversation continuity, response playback and deterministic
session ending.

Phrase: "Hey Aria". The single word "Aria" is NOT accepted as the production
wake phrase (it sounds like "area"; docs/WAKE_PHRASE_LAB.md) and the
listener refuses to start with a single-word ARIA keyword file unless
ARIA_WAKE_ALLOW_SINGLE_WORD=1 (comparison testing only).

A trigger, not a conversation participant (docs/ARIA_WAKE_WORD_ARCHITECTURE.md).
It reads the room's audio capture endpoint (the eMeet, via PulseAudio - a
shared, non-exclusive tap), runs the on-device keyword spotter in detector.py,
and tells the room page over a localhost-only WebSocket that the phrase was
heard. The page then starts the existing Realtime session through its normal
path. Nothing here claims leases, mints sessions, calls OpenAI, stores audio,
or transcribes speech. Every event is one JSON line on stdout (see
wake_stats.py).

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
import websockets

from levels import LevelTracker
from detector import (CHUNK, DEFAULT_KEYWORDS, DEFAULT_SCORE, DEFAULT_THRESHOLD, SAMPLE_RATE,  # noqa: F401
                      SilenceReset, StreamDetector, build_spotter, keyword_labels, spot)

HOST = "127.0.0.1"  # never bind beyond this machine
PORT = int(os.environ.get("ARIA_WAKE_PORT", "8765"))
ORIGINS = [o.strip() for o in os.environ.get(
    "ARIA_WAKE_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
MODEL_DIR = os.environ.get("ARIA_WAKE_MODEL_DIR", os.path.join(os.path.dirname(__file__), "model"))
KEYWORDS_FILE = os.environ.get("ARIA_WAKE_KEYWORDS", DEFAULT_KEYWORDS)
KEYWORDS_SCORE = float(os.environ.get("ARIA_WAKE_KEYWORDS_SCORE", str(DEFAULT_SCORE)))
KEYWORDS_THRESHOLD = float(os.environ.get("ARIA_WAKE_KEYWORDS_THRESHOLD", str(DEFAULT_THRESHOLD)))
GAIN_DB = float(os.environ.get("ARIA_WAKE_GAIN_DB", "0"))   # input boost before the detector (default none)
SOURCE = os.environ.get("ARIA_WAKE_SOURCE", "")  # PulseAudio source; empty = system default
PENDING_WAKE_TIMEOUT_S = 20   # page never confirmed a conversation -> resume listening
RESUME_COOLDOWN_S = 1.5       # ignore the tail of Aria's last words after a session ends


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(event, **fields):
    print(json.dumps({"at": now_iso(), "event": event, **fields}), flush=True)


def resolve_source():
    if SOURCE:
        return SOURCE
    out = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True)
    return out.stdout.strip() or "@DEFAULT_SOURCE@"


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
                "phrase": phrase_text(keyword_labels(KEYWORDS_FILE)), "keywords_file": os.path.basename(KEYWORDS_FILE), "keywords_score": KEYWORDS_SCORE, "keywords_threshold": KEYWORDS_THRESHOLD, "gain_db": GAIN_DB,
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
        det = StreamDetector(build_spotter(MODEL_DIR, KEYWORDS_FILE, KEYWORDS_THRESHOLD, KEYWORDS_SCORE), GAIN_DB)
        levels = LevelTracker(GAIN_DB)
        cmd = ["parec", "--raw", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1",
               "--latency-msec=100", f"--device={self.device}"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        log("capture_started", device=self.device, cmd=" ".join(cmd))
        nbytes = CHUNK * 2
        while True:
            buf = proc.stdout.read(nbytes)
            if not buf:
                log("capture_ended", returncode=proc.poll())
                os._exit(1)  # let the service manager restart us; never run deaf
            if self.state.reset_stream:
                self.state.reset_stream = False
                det.reset()
            samples = np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
            kw = det.feed(samples)
            seg = levels.update(samples, self.state.mode)   # raw level, before gain; numbers only
            if kw:
                levels.note_detection(suppressed=self.state.mode != "listening")
                self.on_detect(kw)
            if seg:
                log("audio_level", **seg)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        threading.Thread(target=self.audio_loop, daemon=True).start()
        async with websockets.serve(self.handler, HOST, PORT, origins=ORIGINS):
            log("serving", host=HOST, port=PORT, origins=ORIGINS, **self.info())
            await asyncio.Future()


ENABLE_ENV = "ARIA_WAKE_ENABLE"
ENABLE_ENV_ALIAS = "ARIA_WAKE_ENABLE_LEGACY"   # earlier name, still honoured
SINGLE_WORD_ENV = "ARIA_WAKE_ALLOW_SINGLE_WORD"


def phrase_text(labels):
    """'HEY_ARIA' -> 'Hey Aria' (for logs and the hello frame)."""
    return " / ".join(l.replace("_", " ").title() for l in labels)


def endpoint_enabled(env=None) -> bool:
    """Off unless explicitly enabled - never part of standard room provisioning."""
    e = env if env is not None else os.environ
    return e.get(ENABLE_ENV) == "1" or e.get(ENABLE_ENV_ALIAS) == "1"


legacy_enabled = endpoint_enabled   # kept for older callers


def phrase_problem(labels, env=None):
    """None if the keyword file is acceptable, else why the listener must not start."""
    e = env if env is not None else os.environ
    if not labels:
        return "keywords file has no phrase"
    if any(l.upper() == "ARIA" or l.upper().startswith("ARIA_") for l in labels) and e.get(SINGLE_WORD_ENV) != "1":
        return ('single-word "Aria" is not an accepted wake phrase (sounds like "area"); '
                f"use \"Hey Aria\" or set {SINGLE_WORD_ENV}=1 for comparison testing")
    return None


if __name__ == "__main__":
    if not endpoint_enabled():
        print(f"aria_wake: EliteDesk home wake endpoint, disabled by default; "
              f"set {ENABLE_ENV}=1 to run it (see README.md).", file=sys.stderr)
        sys.exit(2)
    labels = keyword_labels(KEYWORDS_FILE)
    problem = phrase_problem(labels)
    if problem:
        log("refused_to_start", reason=problem, keywords_file=KEYWORDS_FILE)
        print(f"aria_wake: {problem}", file=sys.stderr)
        sys.exit(2)
    log("starting", phrase=phrase_text(labels), labels=labels, keywords_file=KEYWORDS_FILE, threshold=KEYWORDS_THRESHOLD,
        score=KEYWORDS_SCORE, gain_db=GAIN_DB, model_dir=MODEL_DIR, origins=ORIGINS)
    try:
        asyncio.run(Server(resolve_source()).run())
    except KeyboardInterrupt:
        sys.exit(0)
