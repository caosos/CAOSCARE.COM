"""Train one Wake Word Lab candidate under the identical recipe.

Follows microWakeWord's basic_training_notebook (augmentation, features,
mixednet, 10k steps) exactly as training/train_model.py, with two lab rules:
- the shared negative features are generated ONCE (seeded) and reused by every
  candidate, so all models see byte-identical negatives;
- Python / NumPy / TensorFlow seeds are fixed (lab_common.SEED) for feature
  generation and training.
Supplemental candidates with `exclude_negatives` (a shared negative phrase with
the SAME SOUND as the candidate, e.g. "Krista" for Krysta) get a negative set
built by the same seeded procedure from the shared negative clips minus those
phrase directories; this is the only deviation and is recorded per model.

usage: train_lab.py <candidate_slug>     (research venv: venv-mww)
"""
import os
import random
import runpy
import sys

import numpy as np
import yaml
from mmap_ninja.ragged import RaggedMmap

from lab_common import RUNS, SAMPLES, SEED, TRAIN_STEPS, WORK, candidate
from microwakeword.audio.augmentation import Augmentation
from microwakeword.audio.clips import Clips
from microwakeword.audio.spectrograms import SpectrogramGeneration

D = WORK / "data"


def seed_all():
    random.seed(SEED)
    np.random.seed(SEED)
    os.environ["PYTHONHASHSEED"] = str(SEED)


def augmenter():
    return Augmentation(
        augmentation_duration_s=3.2,
        augmentation_probabilities={"SevenBandParametricEQ": 0.1, "TanhDistortion": 0.1, "PitchShift": 0.1,
                                    "BandStopFilter": 0.1, "AddColorNoise": 0.1, "AddBackgroundNoise": 0.75,
                                    "Gain": 1.0, "RIR": 0.5},
        impulse_paths=[str(D / "mit_rirs")], background_paths=[str(D / "fma_16k"), str(D / "audioset_16k")],
        background_min_snr_db=-5, background_max_snr_db=10, min_jitter_s=0.195, max_jitter_s=0.205)


def features(src, out_dir, train_repeat):
    if (out_dir / "testing" / "wakeword_mmap").exists():
        return
    seed_all()
    clips = Clips(input_directory=str(src), file_pattern="**/*.wav", max_clip_duration_s=None,
                  remove_silence=False, random_split_seed=10, split_count=0.1)
    aug = augmenter()
    for split, name, rep, slide in (("training", "train", train_repeat, 10), ("validation", "validation", 1, 10),
                                    ("testing", "test", 1, 1)):
        d = out_dir / split
        d.mkdir(parents=True, exist_ok=True)
        gen = SpectrogramGeneration(clips=clips, augmenter=aug, slide_frames=slide, step_ms=10)
        RaggedMmap.from_generator(out_dir=str(d / "wakeword_mmap"),
                                  sample_generator=gen.spectrogram_generator(split=name, repeat=rep),
                                  batch_size=100, verbose=True)


def main(slug):
    run = RUNS / slug
    run.mkdir(parents=True, exist_ok=True)
    shared_neg = RUNS / "_shared_negative_features"
    neg_src = SAMPLES / "train/negatives"
    excl = sorted(candidate(slug).get("exclude_negatives", []))
    if excl:
        names = {"".join(ch if ch.isalnum() else "_" for ch in e.lower()).strip("_")[:48] for e in excl}
        tag = "__minus_" + "_".join(sorted(names))
        filtered = SAMPLES / ("train/negatives" + tag)
        filtered.mkdir(parents=True, exist_ok=True)
        for d in neg_src.iterdir():      # real dirs of hard-linked files: pathlib glob skips symlinked dirs
            if d.name in names:
                continue
            (filtered / d.name).mkdir(exist_ok=True)
            for f in d.glob("*.wav"):
                link = filtered / d.name / f.name
                if not link.exists():
                    os.link(f, link)
        neg_src, shared_neg = filtered, RUNS / ("_shared_negative_features" + tag)
    features(neg_src, shared_neg, 1)
    cand = candidate(slug)
    # method tests (methodtest_candidates.json) reuse another run's positive clips unchanged
    features(SAMPLES / "train/positives" / cand.get("positives_from", slug), run / "positive_features", 2)
    fs = [
        {"features_dir": str(run / "positive_features"), "sampling_weight": 2.0, "penalty_weight": 1.0,
         "truth": True, "truncation_strategy": "truncate_start", "type": "mmap"},
        {"features_dir": str(shared_neg), "sampling_weight": 3.0, "penalty_weight": 1.0,
         "truth": False, "truncation_strategy": "truncate_start", "type": "mmap"},
        *[{"features_dir": str(D / "negative_datasets" / n), "sampling_weight": w, "penalty_weight": 1.0,
           "truth": False, "truncation_strategy": "random", "type": "mmap"}
          for n, w in (("speech", 10.0), ("dinner_party", 10.0), ("no_speech", 5.0))],
        *[{"features_dir": str(WORK / x["features_dir"]), "sampling_weight": x["sampling_weight"],
           "penalty_weight": x["penalty_weight"], "truth": False, "truncation_strategy": x["truncation_strategy"],
           "type": "mmap"} for x in cand.get("extra_negatives", [])],
        {"features_dir": str(D / "negative_datasets/dinner_party_eval"), "sampling_weight": 0.0,
         "penalty_weight": 1.0, "truth": False, "truncation_strategy": "split", "type": "mmap"},
    ]
    cfg = {"window_step_ms": 10, "train_dir": str(run / "trained"), "features": fs,
           "training_steps": [TRAIN_STEPS], "positive_class_weight": [1], "negative_class_weight": [20],
           "learning_rates": [0.001], "batch_size": 128, "time_mask_max_size": [0], "time_mask_count": [0],
           "freq_mask_max_size": [0], "freq_mask_count": [0], "eval_step_interval": 500,
           "clip_duration_ms": 1500, "target_minimization": 0.9, "minimization_metric": None,
           "maximization_metric": "average_viable_recall", "seed": SEED,
           "excluded_same_sound_negatives": excl, "extra_negatives": cand.get("extra_negatives", []),
           "positives_from": cand.get("positives_from", slug)}
    (run / "training_parameters.yaml").write_text(yaml.dump(cfg))
    os.chdir(run)
    seed_all()
    import tensorflow as tf
    tf.random.set_seed(SEED)
    sys.argv = ["model_train_eval", "--training_config=training_parameters.yaml", "--train", "1",
                "--restore_checkpoint", "1", "--test_tf_nonstreaming", "0", "--test_tflite_nonstreaming", "0",
                "--test_tflite_nonstreaming_quantized", "0", "--test_tflite_streaming", "0",
                "--test_tflite_streaming_quantized", "1", "--use_weights", "best_weights",
                "mixednet", "--pointwise_filters", "64,64,64,64", "--repeat_in_block", "1, 1, 1, 1",
                "--mixconv_kernel_sizes", "[5], [7,11], [9,15], [23]", "--residual_connection", "0,0,0,0",
                "--first_conv_filters", "32", "--first_conv_kernel_size", "5", "--stride", "3"]
    runpy.run_module("microwakeword.model_train_eval", run_name="__main__")
    print("TRAINED", slug)


if __name__ == "__main__":
    main(sys.argv[1])
