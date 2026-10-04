"""Train one microWakeWord model, following the official basic training
notebook (augmentation, feature generation, config, mixednet architecture),
with sound-alike hard negatives added as an extra negative feature set.

usage: train_model.py <naboo|hey_naboo> [training_steps]
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml
from mmap_ninja.ragged import RaggedMmap

from microwakeword.audio.augmentation import Augmentation
from microwakeword.audio.clips import Clips
from microwakeword.audio.spectrograms import SpectrogramGeneration

W = Path(__file__).parent.resolve()
D = W / "data"
NAME = sys.argv[1]
STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
RUN = W / "runs" / NAME
RUN.mkdir(parents=True, exist_ok=True)
os.chdir(RUN)

NEGATIVE_TTS = ["adversarial"] + (["bare_naboo_negative"] if NAME == "hey_naboo" else [])


def augmenter():
    # Notebook settings.
    return Augmentation(
        augmentation_duration_s=3.2,
        augmentation_probabilities={
            "SevenBandParametricEQ": 0.1, "TanhDistortion": 0.1, "PitchShift": 0.1,
            "BandStopFilter": 0.1, "AddColorNoise": 0.1, "AddBackgroundNoise": 0.75,
            "Gain": 1.0, "RIR": 0.5,
        },
        impulse_paths=[str(D / "mit_rirs")],
        background_paths=[str(D / "fma_16k"), str(D / "audioset_16k")],
        background_min_snr_db=-5, background_max_snr_db=10,
        min_jitter_s=0.195, max_jitter_s=0.205,
    )


def features(src_dirs, out_dir, train_repeat):
    """Augmented spectrogram features, train/validation/test splits (notebook)."""
    if (out_dir / "testing" / "wakeword_mmap").exists():
        return
    clips = Clips(input_directory=str(src_dirs[0]), file_pattern="**/*.wav",
                  max_clip_duration_s=None, remove_silence=False,
                  random_split_seed=10, split_count=0.1)
    if len(src_dirs) > 1:  # several source dirs: use their common parent
        clips = Clips(input_directory=str(src_dirs[0].parent), file_pattern="**/*.wav",
                      max_clip_duration_s=None, remove_silence=False,
                      random_split_seed=10, split_count=0.1)
    aug = augmenter()
    for split, split_name, rep, slide in (("training", "train", train_repeat, 10),
                                          ("validation", "validation", 1, 10),
                                          ("testing", "test", 1, 1)):
        d = out_dir / split
        d.mkdir(parents=True, exist_ok=True)
        gen = SpectrogramGeneration(clips=clips, augmenter=aug, slide_frames=slide, step_ms=10)
        RaggedMmap.from_generator(out_dir=str(d / "wakeword_mmap"),
                                  sample_generator=gen.spectrogram_generator(split=split_name, repeat=rep),
                                  batch_size=100, verbose=True)


features([W / "samples/train" / NAME], RUN / "positive_features", 2)
for neg in NEGATIVE_TTS:
    features([W / "samples/train" / neg], RUN / f"{neg}_features", 1)

feature_sets = [
    {"features_dir": str(RUN / "positive_features"), "sampling_weight": 2.0, "penalty_weight": 1.0,
     "truth": True, "truncation_strategy": "truncate_start", "type": "mmap"},
    *[{"features_dir": str(RUN / f"{neg}_features"), "sampling_weight": 3.0, "penalty_weight": 1.0,
       "truth": False, "truncation_strategy": "truncate_start", "type": "mmap"} for neg in NEGATIVE_TTS],
    {"features_dir": str(D / "negative_datasets/speech"), "sampling_weight": 10.0, "penalty_weight": 1.0,
     "truth": False, "truncation_strategy": "random", "type": "mmap"},
    {"features_dir": str(D / "negative_datasets/dinner_party"), "sampling_weight": 10.0, "penalty_weight": 1.0,
     "truth": False, "truncation_strategy": "random", "type": "mmap"},
    {"features_dir": str(D / "negative_datasets/no_speech"), "sampling_weight": 5.0, "penalty_weight": 1.0,
     "truth": False, "truncation_strategy": "random", "type": "mmap"},
    {"features_dir": str(D / "negative_datasets/dinner_party_eval"), "sampling_weight": 0.0, "penalty_weight": 1.0,
     "truth": False, "truncation_strategy": "split", "type": "mmap"},
]
config = {
    "window_step_ms": 10, "train_dir": str(RUN / "trained"), "features": feature_sets,
    "training_steps": [STEPS], "positive_class_weight": [1], "negative_class_weight": [20],
    "learning_rates": [0.001], "batch_size": 128,
    "time_mask_max_size": [0], "time_mask_count": [0], "freq_mask_max_size": [0], "freq_mask_count": [0],
    "eval_step_interval": 500, "clip_duration_ms": 1500,
    "target_minimization": 0.9, "minimization_metric": None,
    "maximization_metric": "average_viable_recall",
}
(RUN / "training_parameters.yaml").write_text(yaml.dump(config))

subprocess.run([
    sys.executable, "-m", "microwakeword.model_train_eval",
    "--training_config=training_parameters.yaml", "--train", "1", "--restore_checkpoint", "1",
    "--test_tf_nonstreaming", "0", "--test_tflite_nonstreaming", "0",
    "--test_tflite_nonstreaming_quantized", "0", "--test_tflite_streaming", "0",
    "--test_tflite_streaming_quantized", "1", "--use_weights", "best_weights",
    "mixednet", "--pointwise_filters", "64,64,64,64", "--repeat_in_block", "1, 1, 1, 1",
    "--mixconv_kernel_sizes", "[5], [7,11], [9,15], [23]", "--residual_connection", "0,0,0,0",
    "--first_conv_filters", "32", "--first_conv_kernel_size", "5", "--stride", "3",
], check=True)
print("TRAINED", NAME)
