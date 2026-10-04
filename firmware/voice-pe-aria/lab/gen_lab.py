"""Generate Wake Word Lab audio under identical, seeded conditions.

  negatives   shared training negatives (identical set for every model)
  positives   per-candidate training positives: 3 pronunciation forms x
              TRAIN_POSITIVES_PER_FORM, synthesised from the candidate's exact
              phonemes (no spelling guesswork), seeded per (candidate, form)
  eval        held-out evaluation clips from 24 named speakers of Piper VITS
              voices never used in training (positives for every candidate,
              shared negatives, held-out neighbours, held-out sentences)

Training generator: Piper LibriTTS-R multi-speaker (.pt, piper-sample-generator).
Run with the research venv (venv-mww). Output under ~/caoscare-firmware-work/samples/lab.
usage: gen_lab.py negatives|positives|eval
"""
import json
import sys
import wave
import zlib

import numpy as np
import torch

from lab_common import (EVAL_LENGTH_SCALES, EVAL_SENTENCES, EVAL_SPEAKERS, FORMS, GEN_PT, LENGTH_SCALES,
                        NOISE_SCALES, NOISE_WS, SAMPLES, SEED, TRAIN_NEGATIVES_PER_PHRASE,
                        TRAIN_POSITIVES_PER_FORM, VOICES, ipa_phrase, load_trained_candidates,
                        training_negative_phrases)

sys.path.insert(0, str(GEN_PT.parents[1]))
from piper_sample_generator.__main__ import generate_samples  # noqa: E402


def slug(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s.lower()).strip("_")[:48]


def seeded(tag):
    s = (SEED + zlib.crc32(tag.encode())) % (2 ** 31)
    torch.manual_seed(s)
    np.random.seed(s)
    return s


def gen_pt(text, out, n, phonemes, tag):
    out.mkdir(parents=True, exist_ok=True)
    if len(list(out.glob("*.wav"))) >= n:
        return
    seeded(tag)
    generate_samples(text=text, output_dir=out, model=str(GEN_PT), max_samples=n, batch_size=50,
                     slerp_weights=(0.5,), length_scales=LENGTH_SCALES, noise_scales=NOISE_SCALES,
                     noise_scale_ws=NOISE_WS, phoneme_input=phonemes)


def negatives():
    nb = json.loads((SAMPLES.parent.parent / "lab_neighbours.json").read_text()) \
        if (SAMPLES.parent.parent / "lab_neighbours.json").exists() else {"train": []}
    phrases = training_negative_phrases(nb["train"])
    for p in phrases:
        gen_pt(p, SAMPLES / "train/negatives" / slug(p), TRAIN_NEGATIVES_PER_PHRASE, False, "neg|" + p)
    print("negatives:", len(phrases), "phrases")


def positives():
    for c in load_trained_candidates():
        for form in FORMS:
            ipa = ipa_phrase(c["arpa_words"], form)
            gen_pt(ipa, SAMPLES / "train/positives" / c["slug"] / form, TRAIN_POSITIVES_PER_FORM, True,
                   f"pos|{c['slug']}|{form}")
        print("positives:", c["slug"], flush=True)


_VOICE_CACHE = {}


def synth_onnx(voice_name, speaker, text, out_path, length_scale, phonemes=False):
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    v = _VOICE_CACHE.get(voice_name) or PiperVoice.load(str(VOICES / f"{voice_name}.onnx"))
    _VOICE_CACHE[voice_name] = v
    sid = None
    if speaker is not None:
        smap = v.config.speaker_id_map or {}
        sid = smap.get(speaker, int(speaker) if str(speaker).isdigit() else 0)
    cfg = SynthesisConfig(speaker_id=sid, length_scale=length_scale, noise_scale=0.667, noise_w_scale=0.8)
    if phonemes:
        ids = v.phonemes_to_ids(list(text.replace(" ", " ")))
    else:
        ids = []
        for sent in v.phonemize(text):
            ids += v.phonemes_to_ids(sent)
    audio = v.phoneme_ids_to_audio(ids, cfg)
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(v.config.sample_rate)
        w.writeframes(pcm.tobytes())


def eval_set():
    """Every clip is (set, item, speaker, length) - identical for all models."""
    cands = load_trained_candidates()
    nb = json.loads((SAMPLES.parent.parent / "lab_neighbours.json").read_text())
    jobs = []
    for c in cands:
        for form in FORMS:
            jobs.append(("positives/" + c["slug"] + "/" + form, ipa_phrase(c["arpa_words"], form), True))
        for alt in c.get("alt_pronunciations", []):   # pronunciation-sensitivity diagnostics
            jobs.append(("pronunciation/" + c["slug"] + "/" + slug(alt["label"]),
                         ipa_phrase(alt["arpa_words"], "intended"), True))
    for p in training_negative_phrases(nb["train"]):
        jobs.append(("negatives_trained/" + slug(p), p, False))
    for p in nb["eval"]:
        jobs.append(("negatives_heldout/" + slug(p), p, False))
    for s in EVAL_SENTENCES:
        jobs.append(("sentences/" + slug(s), s, False))
    base = SAMPLES / "eval"
    total = 0
    for rel, text, ph in jobs:
        d = base / rel
        d.mkdir(parents=True, exist_ok=True)
        for voice, spk, label, _sex in EVAL_SPEAKERS:
            for ls in EVAL_LENGTH_SCALES if rel.startswith(("positives", "pronunciation")) else (1.0,):
                f = d / f"{slug(label)}__ls{ls}.wav"
                if not f.exists():
                    synth_onnx(voice, spk, text, f, ls, ph)
                total += 1
    print("eval clips:", total)


if __name__ == "__main__":
    {"negatives": negatives, "positives": positives, "eval": eval_set}[sys.argv[1]]()
