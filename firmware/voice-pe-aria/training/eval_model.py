"""Offline evaluation of a trained microWakeWord streaming model on HELD-OUT
synthetic clips (Piper VITS voices never used for training), under several
simulated listening conditions.

Detection rule mirrors ESPHome's micro_wake_word: the quantized streaming
model emits one probability per 30 ms; a wake is declared when the mean of
the last `WINDOW` probabilities exceeds the cutoff.

Sets (samples/eval/...):
  positives      the model's own phrase, AR-ee-uh respellings
  other_phrase   the other candidate ("Aria" for hey_aria, "Hey Aria" for aria)
  air_ee_uh      plain "Aria"/"Hey Aria" as TTS reads it (/ˈɛɹiə/, = "area");
                 diagnostic only, counted neither as hit nor false accept
  adversarial    sound-alikes (required confusions + held-out ones)
  sentences      held-out ordinary sentences containing similar sounds

Conditions (applied to every clip; speaking speed already varies 0.8-1.25x
in generation):
  clean, quiet_-12dB, very_quiet_-24dB,
  room_1m, room_2m, room_4m  (simulated 5 x 4.5 x 2.7 m room, wall
                              absorption 0.25; direct-path peak scaled to
                              1/distance, reverberant tail as simulated),
  room_4m_noise_10dB         (4 m plus a background-noise clip at 10 dB SNR)

usage: eval_model.py <run_name> [cutoff ...]
"""
import json
import random
import sys
from math import gcd
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve, resample_poly

W = Path(__file__).parent.resolve()
RUN = sys.argv[1]
CUTOFFS = [float(c) for c in sys.argv[2:]] or [0.5, 0.7, 0.8, 0.9, 0.95, 0.97]
WINDOW = 5
TFLITE = W / "runs" / RUN / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
EVAL = W / "samples/eval"
NOISE_DIR = W / "data/audioset_16k"
PAD_BEFORE_S, PAD_AFTER_S = 1.0, 0.8
OTHER = {"aria": "hey_aria", "hey_aria": "aria"}
SETS = {"positives": RUN, "other_phrase": OTHER[RUN], "air_ee_uh": "air_ee_uh",
        "adversarial": "adversarial_aria", "sentences": "sentences_aria"}
CONDITIONS = ["clean", "quiet_-12dB", "very_quiet_-24dB", "room_1m", "room_2m",
              "room_4m", "room_4m_noise_10dB"]


def _rirs():
    import pyroomacoustics as pra
    out = {}
    for d in (1.0, 2.0, 4.0):
        room = pra.ShoeBox([5.0, 4.5, 2.7], fs=16000, max_order=12,
                           materials=pra.Material(0.25), air_absorption=True)
        mic = [0.4, 2.25, 1.0]          # device on a dresser near a wall
        src = [0.4 + d, 2.25, 1.2]      # talker d metres away
        room.add_source(src)
        room.add_microphone(mic)
        room.compute_rir()
        rir = np.asarray(room.rir[0][0], dtype=np.float64)
        # Scale so the direct-path peak is 1/d (1 m == unity); the reverberant
        # tail keeps its simulated level relative to the direct sound.
        rir *= (1.0 / d) / np.abs(rir).max()
        out[d] = rir
    return out


RIRS = None
NOISES = None


def _init():
    global RIRS, NOISES, MODEL
    from microwakeword.inference import Model
    RIRS = _rirs()
    NOISES = sorted(NOISE_DIR.glob("*.wav"))
    MODEL = Model(str(TFLITE))


def load16k(path):
    a, sr = sf.read(str(path), always_2d=True)
    a = a.mean(axis=1)
    if sr != 16000:
        g = gcd(sr, 16000)
        a = resample_poly(a, 16000 // g, sr // g)
    return a


def apply(a, cond, rng):
    if cond == "quiet_-12dB":
        return a * 10 ** (-12 / 20)
    if cond == "very_quiet_-24dB":
        return a * 10 ** (-24 / 20)
    if cond.startswith("room_"):
        d = float(cond.split("_")[1][:-1])
        # TTS clips are normalised to full scale; start the talker at a
        # moderate level (-8 dB) so the 1 m case does not clip.
        y = fftconvolve(a * 0.4, RIRS[d])[: len(a) + 8000]
        if cond.endswith("noise_10dB"):
            n = load16k(rng.choice(NOISES))
            if len(n) < len(y):
                n = np.tile(n, int(np.ceil(len(y) / len(n))))
            n = n[: len(y)]
            ps, pn = np.mean(y ** 2) + 1e-12, np.mean(n ** 2) + 1e-12
            y = y + n * np.sqrt(ps / (pn * 10 ** (10 / 10)))
        return y
    return a


def peak_score(job):
    path, cond = job
    rng = random.Random(hash((str(path), cond)) & 0xFFFFFFFF)
    a = apply(load16k(path), cond, rng)
    pad = lambda s: np.zeros(int(s * 16000))
    a = np.concatenate([pad(PAD_BEFORE_S), a, pad(PAD_AFTER_S)])
    a = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    MODEL.__init__(str(TFLITE))  # fresh streaming state per clip
    p = np.array(MODEL.predict_clip(a, step_ms=10), dtype=np.float32)
    if len(p) < WINDOW:
        return float(p.max()) if len(p) else 0.0
    return float(np.convolve(p, np.ones(WINDOW) / WINDOW, mode="valid").max())


def main():
    groups = {}  # set -> subdir -> [files]
    for name, sub in SETS.items():
        d = EVAL / sub
        groups[name] = {s.name: sorted(s.glob("*.wav")) for s in sorted(d.iterdir()) if s.is_dir()}
    jobs = [(f, c) for c in CONDITIONS for g in groups.values() for fs in g.values() for f in fs]
    with Pool(4, initializer=_init) as pool:
        scores = dict(zip(jobs, pool.map(peak_score, jobs, chunksize=16)))

    res = {"model": RUN, "tflite_bytes": TFLITE.stat().st_size, "window": WINDOW,
           "conditions": CONDITIONS, "scores": {}}
    for c in CONDITIONS:
        res["scores"][c] = {name: {sub: [round(scores[(f, c)], 4) for f in fs]
                                   for sub, fs in g.items()} for name, g in groups.items()}

    def count(c, name, cut):
        v = [s for lst in res["scores"][c][name].values() for s in lst]
        return sum(s > cut for s in v), len(v)

    summary = []
    for cut in CUTOFFS:
        for c in CONDITIONS:
            row = {"cutoff": cut, "condition": c}
            for name in SETS:
                k, n = count(c, name, cut)
                row[name] = f"{k}/{n}"
            summary.append(row)
    res["summary"] = summary
    out = W / "runs" / RUN / "heldout_eval.json"
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(summary[:len(CONDITIONS)], indent=1))


if __name__ == "__main__":
    main()
