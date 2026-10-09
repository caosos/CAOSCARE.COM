"""Near-miss evidence: how loud was the room audio around a (possible) wake?

The sherpa-onnx keyword spotter only fires or stays silent. As of sherpa-onnx
1.13.8 its Python result carries the keyword string, tokens and timestamps but
NO per-keyword score, so a "near miss" cannot be scored. What can be recorded,
cheaply and without keeping any audio, is the input level: if Michael has to say
"Hey Aria" three times, the log shows whether each attempt was quiet (a level
problem) or loud (a detector problem).

LevelTracker watches the RAW capture chunks (before any ARIA_WAKE_GAIN_DB) and
emits ONE summary per active-speech segment (never per frame): peak and mean
level in dBFS, how many 100 ms frames were above the speech threshold, the
adaptive noise floor, the gain in force, how many detections fired inside the
segment and the listener mode. Only these numbers are kept - no samples.
"""
import numpy as np

CHUNK_S = 0.1
SPEECH_ABOVE_FLOOR_DB = 10.0   # a frame is "speech" when this far above the noise floor...
SPEECH_MIN_DBFS = -50.0        # ...and above this absolute level
QUIET_CHUNKS_TO_CLOSE = 5      # 0.5 s of quiet closes a segment
MIN_SPEECH_FRAMES = 2          # ignore clicks shorter than 0.2 s
MAX_SEGMENT_S = 30.0           # a long continuous sound is reported in slices


def dbfs(x):
    return round(20.0 * float(np.log10(max(float(x), 1e-6))), 1)


class LevelTracker:
    def __init__(self, gain_db=0.0, clock=None):
        self.gain_db = gain_db
        self.floor = None           # linear rms noise floor (same tracker as SilenceReset)
        self._reset()
        self.t = 0.0                # seconds of audio seen
        self.clock = clock

    def _reset(self):
        self.active = False
        self.quiet = 0
        self.start_t = 0.0
        self.speech_frames = 0
        self.frames = 0
        self.peak = 0.0
        self.clipped = 0
        self.sum_sq = 0.0
        self.detections = 0
        self.mode = None
        self.suppressed = False

    def note_detection(self, suppressed=False):
        """A detector hit landed in the current chunk (counts toward this segment)."""
        self.detections += 1
        self.suppressed = self.suppressed or suppressed

    def update(self, samples, mode="listening"):
        """One raw chunk (float32 -1..1). Returns a summary dict when a segment closes, else None."""
        rms = float(np.sqrt(np.mean(samples * samples)) + 1e-9)
        peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
        self.floor = rms if self.floor is None or rms < self.floor else self.floor * 0.999 + rms * 0.001
        floor_db = dbfs(self.floor)
        is_speech = dbfs(rms) > max(floor_db + SPEECH_ABOVE_FLOOR_DB, SPEECH_MIN_DBFS)
        self.t += CHUNK_S
        out = None
        if is_speech:
            if not self.active:
                self.active, self.start_t, self.mode = True, self.t - CHUNK_S, mode
            self.quiet = 0
            self.speech_frames += 1
        elif self.active:
            self.quiet += 1
        if self.active:
            self.frames += 1
            self.peak = max(self.peak, peak)
            self.sum_sq += rms * rms
            self.clipped += int(peak >= 0.999)
            if self.quiet >= QUIET_CHUNKS_TO_CLOSE or self.t - self.start_t >= MAX_SEGMENT_S:
                out = self._close(floor_db)
        return out

    def _close(self, floor_db):
        seg = None
        if self.speech_frames >= MIN_SPEECH_FRAMES:
            seg = {"duration_s": round(self.frames * CHUNK_S, 1), "speech_frames": self.speech_frames,
                   "peak_dbfs": dbfs(self.peak), "mean_dbfs": dbfs((self.sum_sq / self.frames) ** 0.5),
                   "noise_floor_dbfs": floor_db, "clipped_frames": self.clipped,
                   "gain_db": self.gain_db, "detections": self.detections,
                   "detection_suppressed": self.suppressed, "mode": self.mode}
        self._reset()
        return seg
