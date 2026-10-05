"""Evaluate one trained Wake Word Lab model under identical conditions.

Model under test: the quantized streaming .tflite that runs on the Voice PE.
Detection rule (= ESPHome micro_wake_word): mean of the last 5 probabilities
(30 ms stride) > cutoff. Results are stored for every cutoff in CUTOFFS.

Clip conditions (applied identically to every clip; noise drawn with a fixed
per-clip seed):
  clean, soft_-18dB, very_soft_-30dB         volume
  room_1m, room_2m (= quiet room), room_4m  simulated 5x4.5x2.7 m room
  bed_facing_away_3m                        3 m + head-shadow low-pass 2.5 kHz
  tv_on_2m                                  room_2m + TV dialogue proxy at 5 dB SNR
  other_talker_2m                           room_2m + another talker at 0 dB SNR
  hvac_2m, music_2m, background_2m          room_2m + HVAC / music / DEMAND at 10/5/10 dB
  weak_onset                                first 150 ms of speech faded in (weak first consonant)
  short_final                               last 20% of speech removed (shortened final syllable)
  run_together                              time-compressed 1.3x (syllables run together)
  older_sim                                 pitch -2 semitones and 0.9x tempo (simulation)
  raspy_sim                                 breath noise following the speech envelope + mild distortion (simulation)
  dentures_sim                              smeared 4-8 kHz band (lisp-like sibilants) (simulation)
Ambient streams (false activations per hour, 2 s refractory):
  tv_dialogue (3 h), music (1 h), background (0.5 h), hvac (1 h), silence (0.5 h)

usage: eval_lab.py <candidate_slug>                       (research venv: venv-mww)
       eval_lab.py <slug> --cross-supplemental  additive run written to lab_eval_supp_cross.json:
                                                extra confusion clips (all models) + supplemental
                                                positives (original 15 only); lab_eval.json is
                                                never modified
"""
import json
import random
import sys
import zlib
import time
from math import gcd
from multiprocessing import Pool

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, lfilter, resample_poly

from lab_common import (CUTOFFS, EVAL_DATA, REPORT_CUTOFF, RUNS, SAMPLES, SEED, load_batch_candidates,
                        load_supplemental_candidates, load_trained_candidates, sha256)

SR = 16000
WORKERS = 3      # memory: ~1.4-1.8 GB per worker (TF runtime + int16 noise); 3 keeps the 14 GB host safe
WINDOW = 5
STRIDE_S = 0.03
PAD_BEFORE, PAD_AFTER = 1.0, 0.8
STREAMS = {"tv_dialogue": None, "music": None, "background": None, "hvac": None, "silence": None}
POS_CONDITIONS = ["clean", "soft_-18dB", "very_soft_-30dB", "room_1m", "room_2m", "room_4m",
                  "bed_facing_away_3m", "tv_on_2m", "other_talker_2m", "hvac_2m", "music_2m", "background_2m",
                  "weak_onset", "short_final", "run_together", "older_sim", "raspy_sim", "dentures_sim"]
NEG_CONDITIONS = ["clean", "soft_-18dB", "room_2m", "tv_on_2m", "other_talker_2m"]

_G = {}


def load16k(path):
    a, sr = sf.read(str(path), always_2d=True)
    a = a.mean(axis=1)
    if sr != SR:
        g = gcd(sr, SR)
        a = resample_poly(a, SR // g, sr // g)
    return a.astype(np.float64)


def rirs():
    import pyroomacoustics as pra
    out = {}
    for d in (1.0, 2.0, 3.0, 4.0):
        room = pra.ShoeBox([5.0, 4.5, 2.7], fs=SR, max_order=12, materials=pra.Material(0.25), air_absorption=True)
        room.add_source([0.4 + d, 2.25, 1.2])
        room.add_microphone([0.4, 2.25, 1.0])
        room.compute_rir()
        h = np.asarray(room.rir[0][0], dtype=np.float64)
        out[d] = h * (1.0 / d) / np.abs(h).max()
    return out


def _init(tflite):
    from microwakeword.inference import Model
    _G["tflite"] = tflite
    _G["model"] = Model(tflite)
    _G["rir"] = rirs()
    # int16 storage (16 kHz streams): ~0.65 GB per worker instead of ~2.6 GB as float64
    _G["noise"] = {k: sf.read(str(EVAL_DATA / "streams" / f"{k}.wav"), dtype="int16")[0]
                   for k in ("talker_pool", "music", "background", "hvac", "tv_dialogue")}


def speech_bounds(a):
    env = np.convolve(np.abs(a), np.ones(160) / 160, mode="same")
    idx = np.where(env > 0.02 * env.max())[0]
    return (idx[0], idx[-1]) if len(idx) else (0, len(a))


def lowpass(a, hz):
    return lfilter(*butter(4, hz / (SR / 2)), a)


def mix(sig, noise_key, snr_db, rng):
    n = _G["noise"][noise_key]
    start = rng.integers(0, len(n) - len(sig) - 1)
    n = n[start:start + len(sig)].astype(np.float64) / 32767.0
    ps, pn = np.mean(sig ** 2) + 1e-12, np.mean(n ** 2) + 1e-12
    return sig + n * np.sqrt(ps / (pn * 10 ** (snr_db / 10)))


def room(a, d):
    return fftconvolve(a * 0.4, _G["rir"][d])[: len(a) + 8000]


def apply(a, cond, rng):
    if cond == "clean":
        return a
    if cond.startswith(("soft_", "very_soft_")):
        return a * 10 ** (float(cond.split("_")[-1][:-2]) / 20)
    if cond in ("room_1m", "room_2m", "room_4m"):
        return room(a, float(cond[5]))
    if cond == "bed_facing_away_3m":
        return lowpass(room(a, 3.0), 2500)
    if cond.endswith("_2m"):
        key, snr = {"tv_on_2m": ("tv_dialogue", 5), "other_talker_2m": ("talker_pool", 0),
                    "hvac_2m": ("hvac", 10), "music_2m": ("music", 5), "background_2m": ("background", 10)}[cond]
        return mix(room(a, 2.0), key, snr, rng)
    s, e = speech_bounds(a)
    if cond == "weak_onset":
        b = a.copy()
        n = int(0.15 * SR)
        b[s:s + n] *= np.linspace(0.05, 1.0, min(n, len(b) - s))
        return b
    if cond == "short_final":
        cut = e - int(0.2 * (e - s))
        b = a[:cut].copy()
        b[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))
        return b
    if cond == "run_together":
        import librosa
        return librosa.effects.time_stretch(a.astype(np.float32), rate=1.3).astype(np.float64)
    if cond == "older_sim":
        import librosa
        b = librosa.effects.pitch_shift(a.astype(np.float32), sr=SR, n_steps=-2)
        return librosa.effects.time_stretch(b, rate=0.9).astype(np.float64)
    if cond == "raspy_sim":
        env = np.convolve(np.abs(a), np.ones(320) / 320, mode="same")
        breath = lfilter(*butter(2, [1500 / (SR / 2), 6000 / (SR / 2)], "band"), rng.standard_normal(len(a)))
        b = a + breath / (np.abs(breath).max() + 1e-9) * env * 0.6
        return np.tanh(2.0 * b) / 2.0
    if cond == "dentures_sim":
        hi = lfilter(*butter(4, 4000 / (SR / 2), "high"), a)
        smear = np.convolve(hi, np.hanning(64) / np.hanning(64).sum(), mode="same")
        noise = lfilter(*butter(4, 4000 / (SR / 2), "high"), rng.standard_normal(len(a)))
        env = np.convolve(np.abs(hi), np.ones(160) / 160, mode="same")
        return a - hi + 0.5 * smear + noise * env * 0.5
    raise ValueError(cond)


def scores(a):
    a = np.concatenate([np.zeros(int(PAD_BEFORE * SR)), a, np.zeros(int(PAD_AFTER * SR))])
    pcm = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    m = _G["model"]
    m.__init__(_G["tflite"])
    p = np.array(m.predict_clip(pcm, step_ms=10), dtype=np.float32)
    if len(p) < WINDOW:
        return np.array([p.max() if len(p) else 0.0])
    return np.convolve(p, np.ones(WINDOW) / WINDOW, mode="valid")


def clip_job(job):
    path, cond = job
    # Deterministic per-clip seed, identical for every model and every process. (Was Python's
    # hash(), which is salted per process: each model got different noise offsets - fixed 2026-10-04.)
    key = f"{str(path).split('/samples/lab/eval/')[-1]}|{cond}"
    rng = np.random.default_rng((SEED + zlib.crc32(key.encode())) % (2 ** 32))
    a = apply(load16k(path), cond, rng)
    w = scores(a)
    lat = None
    if cond == "clean":
        s, e = speech_bounds(load16k(path))
        end_t = PAD_BEFORE + e / SR
        above = np.where(w > REPORT_CUTOFF)[0]
        if len(above):
            t = (above[0] + WINDOW) * STRIDE_S
            lat = round((t - end_t) * 1000, 1)
    return path, cond, float(w.max()), lat


def stream_job(name):
    path = EVAL_DATA / "streams" / f"{name}.wav"
    chunk = 600 * SR
    total = sf.info(str(path)).frames
    events = {c: 0 for c in CUTOFFS}
    t0 = time.time()
    frames = 0
    for block in sf.blocks(str(path), blocksize=chunk, dtype="float64"):   # 10-min chunks, low memory
        w = scores(block)
        frames += len(w)
        for c in CUTOFFS:
            hits = np.where(w > c)[0]
            last = -1e9
            for h in hits:
                if h - last >= 2.0 / STRIDE_S:
                    events[c] += 1
                    last = h
    hours = total / SR / 3600
    return name, {"hours": round(hours, 3), "events": events,
                  "per_hour": {c: round(n / hours, 3) for c, n in events.items()},
                  "host_ms_per_inference": round((time.time() - t0) * 1000 / max(1, frames), 4)}


def arena(tflite):
    import subprocess
    out = subprocess.run([sys.executable, "-c", "from tflite_micro.python.tflite_micro import runtime;"
                          f"runtime.Interpreter.from_file('{tflite}', arena_size=200000).print_allocations()"],
                         capture_output=True, text=True)
    for line in (out.stdout + out.stderr).splitlines():
        if "Arena allocation total" in line:
            return int(line.split()[-2])
    return None


def cross_supplemental(slug, tflite, is_original):
    """Additive evaluation written to lab_eval_supp_cross.json (lab_eval.json is never touched):
    - every model: the extra held-out confusion clips (eval/negatives_extra) under NEG_CONDITIONS
    - original 15 only: the supplemental candidates' clean positives (cross-trigger)"""
    ev = SAMPLES / "eval"
    jobs = [(str(f), c) for f in sorted((ev / "negatives_extra").rglob("*.wav")) for c in NEG_CONDITIONS]
    if is_original:
        jobs += [(str(f), "clean") for c in load_supplemental_candidates()
                 for f in sorted((ev / "positives" / c["slug"]).rglob("*.wav"))]
    with Pool(WORKERS, initializer=_init, initargs=(tflite,)) as pool:
        clip = pool.map(clip_job, jobs, chunksize=32)
    out = {"candidate": slug, "tflite_sha256": sha256(tflite), "mode": "cross_supplemental",
           "clips": [{"file": str(p).split("/samples/lab/eval/")[-1], "condition": c, "peak": round(s, 4)}
                     for p, c, s, _ in clip]}
    (RUNS / slug / "lab_eval_supp_cross.json").write_text(json.dumps(out))
    print(slug, "cross-supplemental clips", len(clip))


def main(slug, cross=False):
    originals = {c["slug"]: c for c in load_trained_candidates()}
    supplemental = {c["slug"]: c for c in load_supplemental_candidates()}
    batch = {c["slug"]: c for c in load_batch_candidates()}
    method = {c["slug"]: c for c in load_batch_candidates("methodtest")}
    # a method-test model is evaluated exactly as the model it is compared with (eval_as)
    pos = method[slug]["eval_as"] if slug in method else slug
    # original models keep exactly their original job list; supplemental models cross-check all 26;
    # batch models (Round 5) cross-check all 26 plus their own batch
    if slug in batch or slug in method:
        cands = {**originals, **supplemental, **batch}
    else:
        cands = {**originals, **supplemental} if slug in supplemental else originals
    tflite = str(RUNS / slug / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite")
    if cross:
        return cross_supplemental(slug, tflite, slug in originals)
    ev = SAMPLES / "eval"
    jobs = []
    for f in sorted((ev / "positives" / pos).rglob("*.wav")):
        jobs += [(str(f), c) for c in POS_CONDITIONS]
    for other in cands:
        if other != pos:
            jobs += [(str(f), "clean") for f in sorted((ev / "positives" / other).rglob("*.wav"))]
    for f in sorted((ev / "pronunciation" / pos).rglob("*.wav")) if (ev / "pronunciation" / pos).exists() else []:
        jobs += [(str(f), c) for c in ("clean", "room_2m")]
    for sub in ("negatives_trained", "negatives_heldout", "sentences"):
        for f in sorted((ev / sub).rglob("*.wav")):
            jobs += [(str(f), c) for c in NEG_CONDITIONS]
    random.Random(SEED).shuffle(jobs)
    t0 = time.time()
    with Pool(WORKERS, initializer=_init, initargs=(tflite,)) as pool:
        clip = pool.map(clip_job, jobs, chunksize=32)
        streams = dict(pool.map(stream_job, list(STREAMS)))
    out = {"candidate": slug, "tflite": tflite, "tflite_sha256": sha256(tflite),
           "tflite_bytes": __import__("os").path.getsize(tflite), "arena_bytes": arena(tflite),
           "window": WINDOW, "cutoffs": CUTOFFS, "report_cutoff": REPORT_CUTOFF,
           "clips": [{"file": str(p).split("/samples/lab/eval/")[-1], "condition": c, "peak": round(s, 4),
                      "latency_ms": l} for p, c, s, l in clip],
           "streams": streams, "eval_seconds": round(time.time() - t0, 1)}
    (RUNS / slug / "lab_eval.json").write_text(json.dumps(out))
    print(slug, "clips", len(clip), "seconds", out["eval_seconds"])


if __name__ == "__main__":
    main(sys.argv[1], cross="--cross-supplemental" in sys.argv)
