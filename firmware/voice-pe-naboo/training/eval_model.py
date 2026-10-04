"""Offline evaluation of a trained microWakeWord streaming model on HELD-OUT
synthetic clips (Piper voices not used for training).

Detection rule mirrors ESPHome's micro_wake_word: the streaming quantized
model emits one probability per 30 ms (stride 3 x 10 ms features); a wake is
declared when the mean of the last `window` probabilities exceeds `cutoff`.

usage: eval_model.py <run_name> [cutoff ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from microwakeword.inference import Model

W = Path(__file__).parent.resolve()
RUN = sys.argv[1]
CUTOFFS = [float(c) for c in sys.argv[2:]] or [0.5, 0.7, 0.8, 0.9, 0.95, 0.97]
WINDOW = 5
TFLITE = W / "runs" / RUN / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
EVAL = W / "samples/eval"
PAD_BEFORE_S, PAD_AFTER_S = 1.0, 0.6


def load16k(path):
    a, sr = sf.read(str(path), always_2d=True)
    a = a.mean(axis=1)
    if sr != 16000:
        from math import gcd
        g = gcd(sr, 16000)
        a = resample_poly(a, 16000 // g, sr // g)
    pad = lambda s: np.zeros(int(s * 16000))
    a = np.concatenate([pad(PAD_BEFORE_S), a, pad(PAD_AFTER_S)])
    return (np.clip(a, -1, 1) * 32767).astype(np.int16)


def peak_score(model, path):
    model.__init__(str(TFLITE))  # fresh streaming state per clip
    p = np.array(model.predict_clip(load16k(path), step_ms=10), dtype=np.float32)
    if len(p) < WINDOW:
        return float(p.max()) if len(p) else 0.0
    return float(np.convolve(p, np.ones(WINDOW) / WINDOW, mode="valid").max())


def score_dir(model, d):
    out = {}
    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        out[sub.name] = [peak_score(model, f) for f in sorted(sub.glob("*.wav"))]
    return out


def rate(scores, cutoff):
    flat = [s for v in scores.values() for s in v]
    return sum(s > cutoff for s in flat), len(flat)


def main():
    model = Model(str(TFLITE))
    positive_set = "hey_naboo" if RUN == "hey_naboo" else "naboo"
    other_set = "naboo" if RUN == "hey_naboo" else "hey_naboo"
    res = {
        "model": RUN, "tflite_bytes": TFLITE.stat().st_size, "window": WINDOW,
        "positives": score_dir(model, EVAL / positive_set),
        "other_phrase": score_dir(model, EVAL / other_set),
        "adversarial": score_dir(model, EVAL / "adversarial"),
    }
    table = []
    for c in CUTOFFS:
        tp, np_ = rate(res["positives"], c)
        op, no_ = rate(res["other_phrase"], c)
        fa, na = rate(res["adversarial"], c)
        table.append({"cutoff": c, "true_accept": f"{tp}/{np_}", "false_reject_pct": round(100 * (np_ - tp) / np_, 1),
                      "other_phrase_accept": f"{op}/{no_}", "adversarial_false_accept": f"{fa}/{na}"})
    worst = sorted(((max(v), k) for k, v in res["adversarial"].items()), reverse=True)[:8]
    res["summary"] = table
    res["worst_adversarial"] = [{"phrase_voice": k, "peak": round(s, 3)} for s, k in worst]
    out = W / "runs" / RUN / "heldout_eval.json"
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps({"summary": table, "worst_adversarial": res["worst_adversarial"]}, indent=1))


if __name__ == "__main__":
    main()
