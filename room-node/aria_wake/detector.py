"""Wake-phrase detection core (sherpa-onnx keyword spotting), no I/O.

Split out of aria_wake.py so the listener and the offline evaluation
(eval_offline.py) run the SAME detection code: build_spotter(), spot() and
SilenceReset. Needs only numpy and sherpa_onnx (no websockets, no audio device).

Default phrase: "Hey Aria" (Michael, 2026-10-03; the single word "Aria" is
rejected because it sounds like "area" - docs/WAKE_PHRASE_LAB.md).
"""
import os

import numpy as np
import sherpa_onnx

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_RATE = 16000
CHUNK = 1600                  # 100 ms
ENC = "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
DEC = "decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
JOIN = "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
DEFAULT_KEYWORDS = os.path.join(HERE, "keywords.txt")
DEFAULT_THRESHOLD = 0.15      # lab acoustic stage, "hey aria" (docs/WAKE_PHRASE_LAB.md)
DEFAULT_SCORE = 1.0


def keyword_labels(path):
    """Labels ('HEY_ARIA') of a sherpa keywords file; one phrase per line."""
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line.rsplit("@", 1)[1] if "@" in line else line)
    return out


def build_spotter(model_dir, keywords_file=DEFAULT_KEYWORDS, threshold=DEFAULT_THRESHOLD, score=DEFAULT_SCORE):
    m = model_dir
    return sherpa_onnx.KeywordSpotter(
        tokens=f"{m}/tokens.txt", encoder=f"{m}/{ENC}", decoder=f"{m}/{DEC}", joiner=f"{m}/{JOIN}",
        keywords_file=keywords_file, num_threads=1, provider="cpu",
        keywords_score=score, keywords_threshold=threshold,
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


class StreamDetector:
    """One audio stream through the spotter, exactly as the live listener runs it:
    100 ms chunks, reset after a detection, reset at a pause that follows speech.
    The listener (aria_wake.py) and eval_offline.py both use this class."""

    def __init__(self, spotter):
        self.spotter = spotter
        self.stream = spotter.create_stream()
        self.silence = SilenceReset()

    def reset(self):
        self.spotter.reset_stream(self.stream)

    def feed(self, samples):
        """One chunk of float32 mono 16 kHz samples; returns the keyword label if it fired."""
        kw = spot(self.spotter, self.stream, samples)
        if not kw and self.silence.update(samples):
            self.reset()
        return kw

    def run(self, audio):
        """Detection times (seconds) in a clip or long stream."""
        hits = []
        for start in range(0, len(audio), CHUNK):
            if self.feed(audio[start:start + CHUNK]):
                hits.append(start / SAMPLE_RATE)
        return hits
