"""Acoustic + adversarial + soak screening of one candidate (all SYNTHETIC).

  positives   synthetic voices x speaking styles x room conditions -> TRUE / MISSED wake rate
  negatives   adversarial hard negatives (neighbours, traps, Room 214 phrases) -> FALSE wake rate
  soak        hours of ordinary continuous speech (LibriSpeech) -> false wakes per hour
Each is run for every detector setting (candidate at several thresholds, plus
a baseline such as single-word "Aria" at the Room 214 setting) on identical audio.
"""
import datetime
import glob
import os
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from ..corpus.registry import extract_dir
from . import augment, negatives, tts
from .detector import Spotter

STYLES = {
    "neutral": "",
    "soft_elderly_woman": "Speak softly and a little breathily, like a woman in her late eighties. Not loud.",
    "slow_tired_elderly_man": "Speak slowly and tiredly, like a man in his late eighties, slightly slurred.",
    "casual_quick": "Say it quickly and casually, as an offhand call.",
    "calling_across_room": "Call out as if to someone across the room.",
    "hesitant": "Say it hesitantly, with a small pause between the words.",
}
NEG_VOICES = ("alloy", "nova", "onyx", "shimmer")


def _seed(*parts):
    """Stable per-clip seed (Python's hash() is randomised per process)."""
    return zlib.crc32("|".join(parts).encode())


def _librispeech():
    """[(utt_id, transcript, flac_path)] sorted, or [] if not fetched."""
    root = extract_dir("librispeech_test_clean")
    out = []
    for trans in sorted(glob.glob(os.path.join(root, "**", "*.trans.txt"), recursive=True)):
        d = os.path.dirname(trans)
        with open(trans, encoding="utf-8") as fh:
            for line in fh:
                uid, text = line.strip().split(" ", 1)
                out.append((uid, text.lower(), os.path.join(d, uid + ".flac")))
    return out


def _babble(utts, seconds=120):
    import soundfile as sf
    parts, total = [], 0
    for _, _, path in utts[-200:]:
        a, _ = sf.read(path, dtype="float32")
        parts.append(a)
        total += len(a)
        if total > seconds * 16000:
            break
    return np.concatenate(parts) if parts else augment.pink_noise(16000 * seconds, np.random.default_rng(1))


def _synth_all(jobs, workers=6, log=print):
    """jobs: [(key, text, voice, instructions)] -> {key: audio}"""
    def one(j):
        return j[0], tts.synth(j[1], j[2], j[3])
    out = {}
    with ThreadPoolExecutor(workers) as ex:
        for i, (k, a) in enumerate(ex.map(one, jobs), 1):
            out[k] = a
            if i % 50 == 0:
                log(f"    synthesized {i}/{len(jobs)}")
    return out


def positives(spotters, texts, pron_instruction, conds, log=print):
    jobs = [((t, v, s), t, v, (STYLES[s] + " " + pron_instruction).strip())
            for t in texts for v in tts.VOICES for s in STYLES]
    clips = _synth_all(jobs, log=log)
    rows = []
    for (t, v, s), clip in sorted(clips.items()):
        for ci, (cname, fn) in enumerate(conds.items()):
            rng = np.random.default_rng(_seed(t, v, s, cname))
            audio = augment.pad(fn(clip, rng))
            rows.append({"text": t, "voice": v, "style": s, "condition": cname,
                         "hits": {sp.name: bool(sp.run(audio)) for sp in spotters}})
    return rows


def adversarial(spotters, report, conds, log=print):
    items = negatives.build(report)
    jobs = [((text, v), text, v, "") for text, _, _ in items for v in NEG_VOICES]
    clips = _synth_all(jobs, log=log)
    origin = {text: (o, seed) for text, o, seed in items}
    rows = []
    for (text, v), clip in sorted(clips.items()):
        for cname in ("clean", "tv_speech_snr5"):
            rng = np.random.default_rng(_seed(text, v, cname))
            audio = augment.pad(conds[cname](clip, rng))
            rows.append({"text": text, "origin": origin[text][0], "neighbour": origin[text][1],
                         "voice": v, "condition": cname,
                         "hits": {sp.name: bool(sp.run(audio)) for sp in spotters}})
    return rows


def soak(spotters, utts, max_hours=None, log=print):
    """Stream LibriSpeech utterances continuously; count detections per hour."""
    import soundfile as sf
    gap = np.zeros(int(0.3 * 16000), np.float32)
    seconds, events, block, index = 0.0, [], [], []
    limit = max_hours * 3600 if max_hours else None

    def flush():
        if not block:
            return
        audio = np.concatenate(block)
        for sp in spotters:
            for t in sp.run(audio):
                uid, text, _ = next((u for s0, s1, u in index if s0 <= t < s1), ("?", "?", 0))
                events.append({"detector": sp.name, "utterance": uid, "transcript": text})
        block.clear()
        index.clear()

    offset = 0.0
    for n, (uid, text, path) in enumerate(utts, 1):
        a, _ = sf.read(path, dtype="float32")
        dur = len(a) / 16000
        index.append((offset, offset + dur + 0.3, (uid, text, 0)))
        block += [a, gap]
        offset += dur + 0.3
        seconds += dur + 0.3
        if offset > 600:          # decode in ~10-minute blocks
            flush()
            offset = 0.0
            log(f"    soak {seconds / 3600:.2f} h, {len(events)} detections so far")
        if limit and seconds >= limit:
            break
    flush()
    return {"hours": round(seconds / 3600, 3), "utterances": n, "events": events}


def run(candidate, report, spoken_texts, pron_instruction, detector_specs, soak_hours=None, log=print):
    """detector_specs: [(name, keyword_text, threshold)]"""
    t0 = time.time()
    spotters = [Spotter(n, kw, th) for n, kw, th in detector_specs]
    utts = _librispeech()
    conds = augment.conditions(_babble(utts))
    log("  positives ...")
    pos = positives(spotters, spoken_texts, pron_instruction, conds, log)
    log("  adversarial negatives ...")
    neg = adversarial(spotters, report, conds, log)
    log(f"  soak on {len(utts)} LibriSpeech utterances ...")
    sk = soak(spotters, utts, soak_hours, log) if utts else {"hours": 0, "utterances": 0, "events": []}
    return {"candidate": candidate, "label": "SYNTHETIC - not a substitute for real speakers or Room 214 testing",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "detectors": [{"name": n, "keyword": kw, "threshold": th} for n, kw, th in detector_specs],
            "spoken_texts": spoken_texts, "pron_instruction": pron_instruction,
            "styles": STYLES, "conditions": list(conds), "tts_model": tts.MODEL,
            "positives": pos, "negatives": neg, "soak": sk,
            "seconds": round(time.time() - t0, 1)}
