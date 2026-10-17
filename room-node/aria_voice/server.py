"""Aria low-cost voice, room-node half: local turn detection for the room page's cascade transport
(docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md). Holds no provider key; listens on localhost only and calls nothing.
Speech output is not here: the page plays the session's selected voice from the backend (routes/aria_voice.py).

WebSocket ws://127.0.0.1:8794 - one client is one call:
  in   binary                       mic PCM16 mono 16 kHz (the page's echo-cancelled microphone)
  in   {"type":"config", "silence_ms", "threshold"}   turn detection, from the room session's own settings
  out  {"type":"ready"}
  out  {"type":"speech_started"} / {"type":"speech_stopped", "wav": base64 16 kHz WAV of the utterance,
                                         "early_ok": the speech_paused audio is the whole turn}
  out  {"type":"speech_paused", "wav"}   speech went quiet for PAUSE_MS inside a turn: the page may transcribe
                                         early; {"type":"speech_resumed"} if the speaker carries on
  in   config "diagnostics": true        (page opts in; Room 214 measurement only - micLevelTelemetry.js gate)
  out  {"type":"diag", "data": {...}}    numbers only, rate-limited: see Diag
"""
import asyncio
import base64
import collections
import io
import json
import os
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("ARIA_VOICE_MODELS", os.path.join(HERE, "model"))   # silero_vad.onnx (installed by ctl.sh)
PORT = int(os.environ.get("ARIA_VOICE_PORT", "8794"))
MIC_RATE = 16000
PAUSE_MS = int(os.environ.get("ARIA_VOICE_PAUSE_MS", "400"))   # early-transcription point (turn end stays silence_ms)
WIN_MS = 512 * 1000 // MIC_RATE
PREROLL_WINDOWS = 600 // WIN_MS            # the VAD confirms speech ~0.25 s in: keep what came just before
sys.path.insert(0, os.path.join(HERE, "..", "aria_wake"))
from levels import CHUNK_S, LevelTracker   # noqa: E402  the wake listener's level rule, one definition

DIAG_SUMMARY_S = 30                        # frame-continuity summary period
DIAG_MAX_PER_MIN = 30                      # diag messages per minute; the rest are counted, not sent
GAP_MS = 300                               # mic blocks arrive every ~128 ms; a longer silence on the wire is a gap


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


class Diag:
    """Numbers-only evidence of what the detector received and decided, for one call. Answers "was the speech
    in the audio Silero got (after the browser's echo cancellation / noise suppression / AGC), and what did
    Silero do with it". Per closed level segment (levels.LevelTracker on the 16 kHz audio the VAD reads): its
    level numbers, how many 100 ms frames the VAD flagged as speech, whether a turn started in it, and
    no_speech_detected when it had energy but no VAD speech at all. Every DIAG_SUMMARY_S: frame arrival
    (wall vs audio seconds, gaps). sherpa-onnx exposes Silero's speech flag, not its probability, so the score
    here is the flagged-frame count. No samples, no text."""

    def __init__(self, clock=time.monotonic, wall=time.time):
        self.clock, self.wall = clock, wall
        self.levels, self.buf = LevelTracker(), np.zeros(0, dtype=np.float32)
        self.vad_frames = self.turns = 0
        self.t0 = self.epoch0 = self.last = self.summary_at = None
        self.audio_s, self.gaps, self.max_gap_ms, self.dropped = 0.0, 0, 0, 0
        self.sent = collections.deque()

    def _emit(self, now, data):
        while self.sent and now - self.sent[0] > 60:
            self.sent.popleft()
        if len(self.sent) >= DIAG_MAX_PER_MIN:
            self.dropped += 1
            return []
        self.sent.append(now)
        return [{"type": "diag", "data": data}]

    def feed(self, block, vad_speech, turn_started):
        now, out = self.clock(), []
        if self.t0 is None:
            self.t0 = self.summary_at = now; self.epoch0 = self.wall()
        elif self.last is not None:
            gap = round((now - self.last) * 1000)
            if gap > GAP_MS:
                self.gaps += 1; self.max_gap_ms = max(self.max_gap_ms, gap)
        self.last = now
        self.audio_s += len(block) / MIC_RATE
        if turn_started:
            self.turns += 1
        self.buf = np.concatenate([self.buf, block])
        n = int(CHUNK_S * MIC_RATE)
        while len(self.buf) >= n:
            chunk, self.buf = self.buf[:n], self.buf[n:]
            start = self.levels.start_t if self.levels.active else self.levels.t
            seg = self.levels.update(chunk, "vad")
            if self.levels.active and vad_speech:
                self.vad_frames += 1
            if seg:
                out += self._emit(now, {
                    "kind": "energy_segment", "start_epoch_ms": round((self.epoch0 + start) * 1000),
                    "duration_s": seg["duration_s"], "speech_frames": seg["speech_frames"],
                    "peak_dbfs": seg["peak_dbfs"], "mean_dbfs": seg["mean_dbfs"],
                    "noise_floor_dbfs": seg["noise_floor_dbfs"], "clipped_frames": seg["clipped_frames"],
                    "vad_speech_frames": self.vad_frames, "vad_turn_started": self.turns > 0,
                    "no_speech_detected": self.vad_frames == 0 and self.turns == 0})
                self.vad_frames = self.turns = 0
            elif not self.levels.active:
                self.vad_frames = self.turns = 0
        if now - self.summary_at >= DIAG_SUMMARY_S:
            self.summary_at = now
            out += self._emit(now, {"kind": "continuity", "wall_s": round(now - self.t0, 1),
                                    "audio_s": round(self.audio_s, 1), "gaps_over_300ms": self.gaps,
                                    "max_gap_ms": self.max_gap_ms, "diag_dropped": self.dropped})
        return out


class Call:
    def __init__(self, ws):
        self.ws = ws
        self.vad, self.speaking = make_vad(), False
        self.pending = np.zeros(0, dtype=np.float32)
        self.utt, self.peak, self.quiet_ms, self.paused = [], 0.0, 0, False
        self.silence_ms, self.pause_len = 1000, 0
        self.preroll = collections.deque(maxlen=PREROLL_WINDOWS)
        self.diag = None                            # Diag, when the page opts in

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
        vad_speech, started = self.vad.is_speech_detected(), False
        if vad_speech and not self.speaking:
            self.speaking = started = True; out.append({"type": "speech_started"})
            self.utt, self.peak, self.quiet_ms, self.paused = list(self.preroll), 0.0, 0, False
        if self.speaking:
            out += self._pause_watch(block)
        else:
            self.preroll.extend(block.reshape(-1, 512))
        while not self.vad.empty():
            seg = np.asarray(self.vad.front.samples, dtype=np.float32); self.vad.pop()
            # The pause transcript is the whole turn only if nothing was said after that pause: the turn then ended
            # one silence after it. Anything longer - even speech quieter than the pause rule's "sound" - means
            # words came after it, and the page transcribes the complete utterance instead.
            early_ok = bool(self.paused and (len(self.utt) - self.pause_len) * WIN_MS <= self.silence_ms + 300)
            self.speaking = False
            pcm = (np.clip(seg, -1, 1) * 32767).astype("<i2")
            out.append({"type": "speech_stopped", "early_ok": early_ok,
                        "wav": base64.b64encode(wav_bytes(pcm, MIC_RATE)).decode()})
        if self.diag:
            try:
                out += self.diag.feed(block, vad_speech, started)
            except Exception as e:             # diagnostics never affect turn detection: report once, stop
                self.diag = None
                out.append({"type": "diag", "data": {"kind": "diag_failed", "error": type(e).__name__}})
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
            self.diag = Diag() if m.get("diagnostics") is True else None



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
