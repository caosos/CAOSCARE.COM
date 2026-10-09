#!/usr/bin/env python3
"""Threshold / score / input-gain sweep for "Hey Aria" through the REAL listener detector.

Same audio and same detector.StreamDetector as eval_offline.py (SYNTHETIC speech
rebuilt from a Wake Phrase Lab acoustic run's cache, simulated rooms, LibriSpeech
read speech for the soak). One worker process per configuration; nothing is sent
anywhere and a clip missing from the cache is skipped, never requested.

  python eval_sweep.py --run <acoustic run dir> --thresholds 0.05,0.08,0.10,0.12,0.15 \
      --scores 1.0,1.5,2.0 --gains 0 --soak-hours 5.7 --jobs 5 --out sweep.json
  (--gains 6,10 re-runs the grid with ARIA_WAKE_GAIN_DB-style boost; --markdown prints the README tables)

Run with the Wake Phrase Lab venv (numpy, scipy, soundfile, pyyaml, sherpa_onnx).
"""
import argparse
import itertools
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_offline as eo  # noqa: E402  (sets up the wakelab path)
import numpy as np  # noqa: E402

from detector import CHUNK, SAMPLE_RATE, StreamDetector, build_spotter  # noqa: E402

POS, NEG, SOAK_FILES, MODEL_DIR = [], [], [], ""
FAR_QUIET = ("far_reverb", "quiet_-20dB")


def load_clips(run_path, limit):
    from wakelab.audio import augment, evaluate
    tts = eo.cache_only_tts()
    run = eo.load_run(run_path)
    utts = evaluate._librispeech()
    conds = augment.conditions(evaluate._babble(utts))

    def clip(text, voice, instr):
        try:
            return tts.synth(text, voice, instr)
        except eo.CacheMiss:
            return None
    pos, neg, missing = [], [], 0
    for r in (run["positives"][:limit] if limit else run["positives"]):
        c = clip(r["text"], r["voice"], (evaluate.STYLES[r["style"]] + " " + run["pron_instruction"]).strip())
        if c is None:
            missing += 1
            continue
        rng = np.random.default_rng(evaluate._seed(r["text"], r["voice"], r["style"], r["condition"]))
        pos.append((r["condition"], augment.pad(conds[r["condition"]](c, rng)).astype(np.float32)))
    for r in (run["negatives"][:limit] if limit else run["negatives"]):
        c = clip(r["text"], r["voice"], "")
        if c is None:
            missing += 1
            continue
        rng = np.random.default_rng(evaluate._seed(r["text"], r["voice"], r["condition"]))
        neg.append((r["text"], augment.pad(conds[r["condition"]](c, rng)).astype(np.float32)))
    return pos, neg, [(u, t, p) for u, t, p in utts], missing


def run_config(cfg):
    thr, score, gain, soak_hours = cfg
    spotter = build_spotter(MODEL_DIR, os.path.join(HERE, "keywords.txt"), thr, score)
    new = lambda: StreamDetector(spotter, gain)
    by_cond = {}
    for cond, audio in POS:
        k = by_cond.setdefault(cond, [0, 0])
        k[0] += bool(new().run(audio))
        k[1] += 1
    woke = {}
    for text, audio in NEG:
        if new().run(audio):
            woke[text] = woke.get(text, 0) + 1
    events, seconds = 0, 0.0
    if soak_hours:
        import soundfile as sf
        det, gap = new(), np.zeros(int(0.3 * SAMPLE_RATE), np.float32)
        for _uid, _t, path in SOAK_FILES:
            a, _ = sf.read(path, dtype="float32")
            for piece in (a, gap):
                events += sum(bool(det.feed(piece[s:s + CHUNK])) for s in range(0, len(piece), CHUNK))
                seconds += len(piece) / SAMPLE_RATE
            if seconds >= soak_hours * 3600:
                break
    return {"threshold": thr, "score": score, "gain_db": gain, "by_condition": by_cond,
            "adversarial_false": [sum(woke.values()), len(NEG)], "adversarial_woke_on": woke,
            "soak_false_wakes": events, "soak_hours": round(seconds / 3600, 3)}


def pct(k, n):
    return f"{100 * k / n:.0f}%" if n else "n/a"


def markdown(rows):
    out = ["| gain dB | threshold | score | clean | quiet | far | tv@5dB | noise | all | adversarial false | soak false/h |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        bc = r["by_condition"]
        g = lambda c: pct(*bc[c]) if c in bc else "-"
        tk, tn = sum(v[0] for v in bc.values()), sum(v[1] for v in bc.values())
        ph = f"{r['soak_false_wakes'] / r['soak_hours']:.2f}" if r["soak_hours"] else "-"
        out.append(f"| {r['gain_db']:+g} | {r['threshold']} | {r['score']} | {g('clean')} | {g('quiet_-20dB')} | "
                   f"{g('far_reverb')} | {g('tv_speech_snr5')} | {g('noise_snr10')} | {pct(tk, tn)} | "
                   f"{r['adversarial_false'][0]}/{r['adversarial_false'][1]} | {ph} ({r['soak_false_wakes']} in {r['soak_hours']} h) |")
    return "\n".join(out)


def main():
    global POS, NEG, SOAK_FILES, MODEL_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--model-dir", default=os.environ.get("ARIA_WAKE_MODEL_DIR", os.path.join(HERE, "model")))
    ap.add_argument("--thresholds", default="0.05,0.08,0.10,0.12,0.15")
    ap.add_argument("--scores", default="1.0,1.5,2.0")
    ap.add_argument("--gains", default="0")
    ap.add_argument("--soak-hours", type=float, default=0.0, help="0 = skip the soak")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    MODEL_DIR = a.model_dir
    POS, NEG, SOAK_FILES, missing = load_clips(a.run, a.limit)
    if a.limit or not a.soak_hours:
        SOAK_FILES = []
    cfgs = [(float(t), float(s), float(g), a.soak_hours if SOAK_FILES else 0)
            for g, t, s in itertools.product(a.gains.split(","), a.thresholds.split(","), a.scores.split(","))]
    t0 = time.time()
    print(f"{len(POS)} positives, {len(NEG)} adversarial, soak files {len(SOAK_FILES)}, missing cached clips {missing}; "
          f"{len(cfgs)} configs on {a.jobs} workers", flush=True)
    with mp.get_context("fork").Pool(a.jobs) as pool:
        rows = []
        for r in pool.imap(run_config, cfgs):
            rows.append(r)
            print(f"done thr={r['threshold']} score={r['score']} gain={r['gain_db']:+g}  ({time.time() - t0:.0f} s)", flush=True)
    rows.sort(key=lambda r: (r["gain_db"], r["threshold"], r["score"]))
    print("\n" + markdown(rows))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"label": "SYNTHETIC audio through the real listener detector", "missing_cached_clips": missing,
                       "rows": rows, "seconds": round(time.time() - t0, 1)}, fh, indent=2)
        print("wrote", a.out)


if __name__ == "__main__":
    main()
