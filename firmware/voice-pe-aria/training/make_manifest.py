"""Copy a trained model into the firmware worktree with an ESPHome v2 manifest.

usage: make_manifest.py <run_name> <cutoff> <tensor_arena_size>
"""
import json
import shutil
import sys
from pathlib import Path

W = Path.cwd()  # the training work directory (runs/<name>/... lives here)
DEST = Path(__file__).resolve().parent.parent / "models"
WAKE_WORD = {"aria": "Aria", "hey_aria": "Hey Aria"}

run, cutoff, arena = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
src = W / "runs" / run / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
DEST.mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, DEST / f"{run}.tflite")
manifest = {
    "type": "micro",
    "wake_word": WAKE_WORD[run],
    "author": "CAOSCare firmware spike (microWakeWord basic training recipe)",
    "website": "https://github.com/kahrendt/microWakeWord",
    "model": f"{run}.tflite",
    "trained_languages": ["en"],
    "version": 2,
    "micro": {
        "probability_cutoff": cutoff,
        "feature_step_size": 10,
        "sliding_window_size": 5,
        "tensor_arena_size": arena,
        "minimum_esphome_version": "2024.7.0",
    },
}
(DEST / f"{run}.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(DEST / f"{run}.json", (DEST / f"{run}.tflite").stat().st_size, "bytes")
