"""Shadow detector: measure what a more sensitive setting would catch, live,
without changing what wakes Aria.

Optional (ARIA_WAKE_SHADOW_THRESHOLD / _SCORE / _KEYWORDS). A second
StreamDetector reads the same 100 ms chunks as the live one. It never wakes
anything; it only logs how the two disagree, so a real voice in the real room
decides the setting instead of synthetic clips:
  shadow_only  the shadow heard the phrase and the live detector did not
               (a would-be catch of a miss - or a would-be false wake)
  live_only    the live detector fired and the shadow did not
Agreement within WINDOW_S is counted, not logged. Numbers only; no audio is
kept or inspected beyond the detectors themselves.
"""
from detector import CHUNK, SAMPLE_RATE

WINDOW_S = 2.0
_WINDOW_CHUNKS = int(WINDOW_S * SAMPLE_RATE / CHUNK)


class ShadowCompare:
    def __init__(self, detector, describe, log):
        self.det, self.describe, self.log = detector, describe, log
        self.chunk = 0
        self.last_live = None      # chunk index of the last live detection
        self.pending_shadow = None  # chunk index of a shadow hit waiting for a live one
        self.agreed = 0

    def feed(self, samples, live_fired, mode):
        """Call once per chunk, after the live detector, with whether it fired."""
        self.chunk += 1
        if live_fired:
            if self.pending_shadow is not None:
                self.pending_shadow, self.agreed = None, self.agreed + 1
            else:
                self.last_live = self.chunk
        shadow_fired = bool(self.det.feed(samples))
        if shadow_fired:
            if self.last_live is not None and self.chunk - self.last_live <= _WINDOW_CHUNKS:
                self.last_live, self.agreed = None, self.agreed + 1
            else:
                self.pending_shadow = self.chunk
        if self.pending_shadow is not None and self.chunk - self.pending_shadow > _WINDOW_CHUNKS:
            self.pending_shadow = None
            self.log("shadow_only", mode=mode, shadow=self.describe, agreed_so_far=self.agreed)
        if self.last_live is not None and self.chunk - self.last_live > _WINDOW_CHUNKS:
            self.last_live = None
            self.log("live_only", mode=mode, shadow=self.describe, agreed_so_far=self.agreed)
