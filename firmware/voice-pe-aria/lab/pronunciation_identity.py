"""Prove whether two pronunciations of one spelling produce different training audio.

For each pair (e.g. Sivia SIV-ee-uh vs SEE-vee-uh): synthesise N clips per pronunciation with the
training generator using the SAME seed and settings, so the only difference is the phoneme input.
Distance = DTW-aligned mean MFCC distance.
  between    : pronunciation A clip i vs pronunciation B clip i   (same seed -> only the vowel differs)
  within     : pronunciation A seed s vs pronunciation A seed s'  (natural take-to-take variation)
A one-sided Wilcoxon signed-rank test (between > within) decides whether the difference is
measurable. Pronunciations are only consolidated if PROVEN identical; they never are here because
the phoneme inputs differ. Writes results/pronunciation_identity.json.

usage: pronunciation_identity.py   (research venv)
"""
import json
import logging
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch

from scipy.stats import wilcoxon

from gen_lab import generate_samples
from lab_common import GEN_PT, LAB, SEED, ipa_phrase

PAIRS = {"sivia": ("S IH1 V IY0 AH0", "S IY1 V IY0 AH0"),
         "callista": ("K AH0 L IH1 S T AH0", "K AO1 L IH0 S T AH0")}
N = 20


def synth(arpa, seed, out):
    torch.manual_seed(seed)
    np.random.seed(seed)
    generate_samples(text=ipa_phrase([arpa], "intended"), output_dir=out, model=str(GEN_PT), max_samples=N,
                     batch_size=N, slerp_weights=(0.5,), length_scales=(1.0,), noise_scales=(0.667,),
                     noise_scale_ws=(0.8,), phoneme_input=True)
    return [sf.read(out / f"{i}.wav")[0] for i in range(N)]


def mfcc(a):
    return librosa.feature.mfcc(y=np.asarray(a, dtype=np.float32), sr=22050, n_mfcc=13)


def dist(a, b):
    D, wp = librosa.sequence.dtw(mfcc(a), mfcc(b), metric="euclidean")
    return float(D[-1, -1] / len(wp))


def main():
    logging.disable(logging.CRITICAL)
    res = {}
    with tempfile.TemporaryDirectory() as td:
        for word, (pa, pb) in PAIRS.items():
            a1 = synth(pa, SEED, Path(td) / f"{word}_a1")
            b1 = synth(pb, SEED, Path(td) / f"{word}_b1")
            a2 = synth(pa, SEED + 1, Path(td) / f"{word}_a2")
            between = [dist(x, y) for x, y in zip(a1, b1)]
            within = [dist(x, y) for x, y in zip(a1, a2)]
            res[word] = {"pronunciation_a": pa, "pronunciation_b": pb,
                         "ipa_a": ipa_phrase([pa], "intended"), "ipa_b": ipa_phrase([pb], "intended"),
                         "phoneme_inputs_identical": pa.split() == pb.split(),
                         "between_mean": round(float(np.mean(between)), 3),
                         "within_mean": round(float(np.mean(within)), 3),
                         "between_over_within": round(float(np.mean(between) / np.mean(within)), 3),
                         "n_pairs": N,
                         "pairs_between_gt_within": int(sum(b > w for b, w in zip(between, within))),
                         "wilcoxon_p_between_gt_within": float(wilcoxon(between, within, alternative="greater").pvalue)}
            p = res[word]["wilcoxon_p_between_gt_within"]
            res[word]["conclusion"] = (
                "phoneme inputs differ and the audio difference is statistically significant - keep separate"
                if p < 0.05 else
                "phoneme inputs differ but the audio difference is NOT distinguishable from take-to-take "
                "variation at p<0.05 - still trained separately (not proven identical); expect similar models")
            print(word, res[word])
    (LAB / "results/pronunciation_identity.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
