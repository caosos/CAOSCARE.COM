"""Keyword-spotter adapter for acoustic screening.

Mirrors the Room 214 listener's detection loop (room-node/aria_wake/aria_wake.py
at 12dadd4: sherpa-onnx KWS, 100 ms chunks, reset after a detection, silence-
based stream reset). Re-implemented here rather than imported so the lab never
depends on runtime code; keep the two in step if the listener changes.
"""
import os
import re

import numpy as np

from ..config import cache_dir
from ..corpus.registry import extract_dir

SR, CHUNK = 16000, 1600
MODEL_SUBDIR = "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"


def model_dir():
    return os.path.join(extract_dir("sherpa_kws_gigaspeech"), MODEL_SUBDIR)


def keyword_line(text, label):
    """BPE token line for sherpa-onnx, e.g. 'HEY ARIA' -> '▁HE Y ▁A RI A @HEY_ARIA'."""
    import sentencepiece as spm
    sp = spm.SentencePieceProcessor(model_file=os.path.join(model_dir(), "bpe.model"))
    return " ".join(sp.encode(text.upper(), out_type=str)) + f" @{label}"


class SilenceReset:
    QUIET_CHUNKS = 8

    def __init__(self):
        self.floor, self.heard, self.quiet = None, False, 0

    def update(self, x):
        rms = float(np.sqrt(np.mean(x * x)) + 1e-9)
        self.floor = rms if self.floor is None or rms < self.floor else self.floor * 0.999 + rms * 0.001
        if rms > max(self.floor * 3.0, 0.003):
            self.heard, self.quiet = True, 0
            return False
        self.quiet += 1
        if self.heard and self.quiet >= self.QUIET_CHUNKS:
            self.heard = False
            return True
        return False


class Spotter:
    def __init__(self, name, text, threshold, score=1.0):
        import sherpa_onnx
        self.name, self.text, self.threshold, self.score = name, text, threshold, score
        m = model_dir()
        label = re.sub(r"[^A-Z0-9]+", "_", name.upper())
        kw_file = os.path.join(cache_dir(), f"kw_{label}.txt")
        with open(kw_file, "w", encoding="utf-8") as fh:
            fh.write(keyword_line(text, label) + "\n")
        self.kws = sherpa_onnx.KeywordSpotter(
            tokens=f"{m}/tokens.txt",
            encoder=f"{m}/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
            decoder=f"{m}/decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
            joiner=f"{m}/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
            keywords_file=kw_file, num_threads=1, provider="cpu",
            keywords_score=score, keywords_threshold=threshold)

    def run(self, audio):
        """Detection times (seconds) in a mono 16 kHz clip or long stream."""
        stream, sil, hits = self.kws.create_stream(), SilenceReset(), []
        for start in range(0, len(audio), CHUNK):
            x = audio[start:start + CHUNK]
            stream.accept_waveform(SR, x)
            fired = False
            while self.kws.is_ready(stream):
                self.kws.decode_stream(stream)
                if self.kws.get_result(stream):
                    self.kws.reset_stream(stream)
                    hits.append(start / SR)
                    fired = True
            if not fired and sil.update(x):
                self.kws.reset_stream(stream)
        return hits
