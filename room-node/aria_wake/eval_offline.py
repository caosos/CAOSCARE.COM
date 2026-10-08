#!/usr/bin/env python3
"""Offline evaluation of wake phrases through the REAL listener detection path.

Audio is rebuilt from a Wake Phrase Lab acoustic run (tools/wakelab/runs/*/report.json)
and the lab's cached synthetic TTS clips - SYNTHETIC speech, simulated rooms, read
audiobook speech for the soak. Nothing is sent anywhere: a clip missing from the
cache is counted and skipped, never requested. Every detector below is the
listener's own detector.StreamDetector (same chunking, same resets), built from the
same model and keywords files the listener loads.

Run with a Python that has numpy, scipy, soundfile, pyyaml and sherpa_onnx (the lab
venv works), from anywhere:

  python eval_offline.py --run <wakelab run dir or report.json> \
      [--model-dir DIR] [--soak-hours H] [--limit N] [--out results.json]

Detectors compared on IDENTICAL audio: "Hey Aria" (keywords.txt, the default) and
the old single word "Aria" (keywords_aria_single_word.txt). It does not replace
Room 214 testing: it says nothing about the eMeet's real pickup.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "wakelab"))

import numpy as np  # noqa: E402

from detector import CHUNK, SAMPLE_RATE, StreamDetector, build_spotter  # noqa: E402

DETECTORS = {   # name -> keywords file (threshold applies to all, default = the listener's)
    "hey_aria": os.path.join(HERE, "keywords.txt"),
    "aria_single_word": os.path.join(HERE, "keywords_aria_single_word.txt"),
}


class CacheMiss(Exception):
    pass


def cache_only_tts():
    """The lab's tts.synth, but a missing clip raises instead of calling the API."""
    from wakelab.audio import tts

    def refuse(*_a, **_k):
        raise CacheMiss()
    tts._request = refuse
    return tts


def load_run(path):
    p = os.path.join(path, "report.json") if os.path.isdir(path) else path
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)["result"]


def build_all(model_dir, threshold):
    return {n: build_spotter(model_dir, kf, threshold) for n, kf in DETECTORS.items()}


def fresh(spotters, names):
    """A new stream (and silence tracker) per clip on the already-loaded spotter."""
    return {n: StreamDetector(spotters[n]) for n in names}


def hit_any(det, audio):
    return bool(det.run(audio))


def rate(k, n):
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "n/a"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="wakelab run directory (or report.json) of an acoustic run")
    ap.add_argument("--model-dir", default=os.environ.get("ARIA_WAKE_MODEL_DIR", os.path.join(HERE, "model")))
    ap.add_argument("--threshold", type=float, default=0.15)
    ap.add_argument("--soak-hours", type=float, default=None, help="cap the LibriSpeech soak (default: all)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N positives and negatives (quick check)")
    ap.add_argument("--out", default=None, help="write the numbers (not audio) as JSON")
    args = ap.parse_args()

    from wakelab.audio import augment, evaluate  # lab building blocks for the degradations
    tts = cache_only_tts()
    run = load_run(args.run)
    utts = evaluate._librispeech()
    conds = augment.conditions(evaluate._babble(utts))
    names = list(DETECTORS)
    spotters = build_all(args.model_dir, args.threshold)
    t0 = time.time()

    def clip(text, voice, instr):
        try:
            return tts.synth(text, voice, instr)
        except CacheMiss:
            return None

    pos = {n: {"hit": 0, "n": 0, "by_cond": {}} for n in names}
    missing = 0
    rows = run["positives"][: args.limit] if args.limit else run["positives"]
    for r in rows:
        instr = (evaluate.STYLES[r["style"]] + " " + run["pron_instruction"]).strip()
        c = clip(r["text"], r["voice"], instr)
        if c is None:
            missing += 1
            continue
        rng = np.random.default_rng(evaluate._seed(r["text"], r["voice"], r["style"], r["condition"]))
        audio = augment.pad(conds[r["condition"]](c, rng))
        for n, det in fresh(spotters, names).items():
            h = hit_any(det, audio)
            pos[n]["hit"] += h
            pos[n]["n"] += 1
            bc = pos[n]["by_cond"].setdefault(r["condition"], [0, 0])
            bc[0] += h
            bc[1] += 1

    neg = {n: {"hit": 0, "n": 0, "woke_on": {}} for n in names}
    rows = run["negatives"][: args.limit] if args.limit else run["negatives"]
    for r in rows:
        c = clip(r["text"], r["voice"], "")
        if c is None:
            missing += 1
            continue
        rng = np.random.default_rng(evaluate._seed(r["text"], r["voice"], r["condition"]))
        audio = augment.pad(conds[r["condition"]](c, rng))
        for n, det in fresh(spotters, names).items():
            h = hit_any(det, audio)
            neg[n]["hit"] += h
            neg[n]["n"] += 1
            if h:
                neg[n]["woke_on"][r["text"]] = neg[n]["woke_on"].get(r["text"], 0) + 1

    soak = {n: {"events": []} for n in names}
    hours = 0.0
    if utts and not args.limit:
        import soundfile as sf
        gap = np.zeros(int(0.3 * SAMPLE_RATE), np.float32)
        dets = fresh(spotters, names)
        limit = args.soak_hours * 3600 if args.soak_hours else None
        seconds = 0.0
        for uid, text, path in utts:        # one continuous stream per detector, as live
            a, _ = sf.read(path, dtype="float32")
            for piece in (a, gap):
                for n, det in dets.items():
                    for start in range(0, len(piece), CHUNK):
                        if det.feed(piece[start:start + CHUNK]):
                            soak[n]["events"].append({"utterance": uid, "transcript": text})
                seconds += len(piece) / SAMPLE_RATE
            if limit and seconds >= limit:
                break
        hours = seconds / 3600

    result = {"source_run": run["candidate"], "label": "SYNTHETIC audio through the real listener detector; "
              "not a substitute for Room 214 / eMeet testing", "threshold": args.threshold,
              "missing_cached_clips": missing, "soak_hours": round(hours, 3), "detectors": {}}
    for n in names:
        ev = soak[n]["events"]
        result["detectors"][n] = {
            "true_wakes": [pos[n]["hit"], pos[n]["n"]],
            "true_wakes_by_condition": {c: v for c, v in sorted(pos[n]["by_cond"].items())},
            "adversarial_false_wakes": [neg[n]["hit"], neg[n]["n"]],
            "adversarial_lines_that_woke": dict(sorted(neg[n]["woke_on"].items(), key=lambda kv: -kv[1])),
            "soak_false_wakes": len(ev), "soak_false_per_hour": round(len(ev) / hours, 2) if hours else None,
            "soak_events": ev}
    result["seconds"] = round(time.time() - t0, 1)

    print(result["label"])
    print(f"threshold {args.threshold}; missing cached clips: {missing}; soak {result['soak_hours']} h; {result['seconds']} s")
    for n, d in result["detectors"].items():
        print(f"\n{n}")
        print("  true wakes           ", rate(*d["true_wakes"]))
        for c, (k, m) in d["true_wakes_by_condition"].items():
            print(f"    {c:<18}", rate(k, m))
        print("  adversarial false    ", rate(*d["adversarial_false_wakes"]))
        for t, k in list(d["adversarial_lines_that_woke"].items())[:8]:
            print(f"    woke on \"{t}\" x{k}")
        print("  soak false wakes     ", d["soak_false_wakes"], "in", result["soak_hours"], "h =",
              d["soak_false_per_hour"], "per hour")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print("\nwrote", args.out)


if __name__ == "__main__":
    main()
