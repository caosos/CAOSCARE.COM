"""Fetch the augmentation and negative datasets used by the official
microWakeWord basic training notebook (same sources, same processing).

NOTE (from the notebook): these datasets carry mixed licenses and usage
restrictions; models trained with them are for non-commercial personal use.
"""
import os
import subprocess
from pathlib import Path

import numpy as np
import scipy.io.wavfile
import soundfile as sf
from huggingface_hub import snapshot_download
from math import gcd
from scipy.signal import resample_poly
from tqdm import tqdm

ROOT = Path(__file__).parent / "data"
ROOT.mkdir(exist_ok=True)
os.chdir(ROOT)


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def write16k(out_dir, paths, ext):
    # Same result as the notebook's datasets.Audio(sampling_rate=16000) cast:
    # mono, 16 kHz, 16-bit PCM. Decoded with soundfile instead (the current
    # `datasets` release needs torchcodec for audio).
    for path in tqdm(paths):
        try:
            a, sr = sf.read(str(path), always_2d=True)
        except Exception as e:  # a few archive files may be unreadable
            print("skip", path, e)
            continue
        a = a.mean(axis=1)
        if sr != 16000:
            g = gcd(sr, 16000)
            a = resample_poly(a, 16000 // g, sr // g)
        name = Path(path).name.replace(ext, ".wav")
        scipy.io.wavfile.write(os.path.join(out_dir, name), 16000,
                               (np.clip(a, -1, 1) * 32767).astype(np.int16))


if not os.path.exists("mit_rirs"):
    os.mkdir("mit_rirs")
    d = snapshot_download("davidscripka/MIT_environmental_impulse_responses", repo_type="dataset")
    write16k("mit_rirs", sorted(Path(d).glob("16khz/*.wav")), ".wav")

if not os.path.exists("audioset_16k"):
    # The notebook's bal_train09.tar is now published as parquet (same
    # balanced-train subset, shard 09); clips are decoded from the bytes.
    import io
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download
    os.makedirs("audioset/audio", exist_ok=True)
    pf = hf_hub_download("agkphysics/AudioSet", "data/bal_train/09.parquet", repo_type="dataset")
    for row in pq.read_table(pf, columns=["video_id", "audio"]).to_pylist():
        ext = Path(row["audio"]["path"] or "x.flac").suffix or ".flac"
        Path(f"audioset/audio/{row['video_id']}{ext}").write_bytes(row["audio"]["bytes"])
    os.mkdir("audioset_16k")
    paths = sorted(Path("audioset/audio").glob("*"))
    write16k("audioset_16k", paths, paths[0].suffix if paths else ".flac")

if not os.path.exists("fma_16k"):
    os.makedirs("fma", exist_ok=True)
    sh("wget -q -O fma/fma_xs.zip https://huggingface.co/datasets/mchl914/fma_xsmall/resolve/main/fma_xs.zip")
    sh("cd fma && unzip -q fma_xs.zip")
    os.mkdir("fma_16k")
    write16k("fma_16k", sorted(Path("fma/fma_small").glob("**/*.mp3")), ".mp3")

if not os.path.exists("negative_datasets/speech"):
    os.makedirs("negative_datasets", exist_ok=True)
    for fname in ["dinner_party.zip", "dinner_party_eval.zip", "no_speech.zip", "speech.zip"]:
        sh(f"wget -q -O negative_datasets/{fname} "
           f"https://huggingface.co/datasets/kahrendt/microwakeword/resolve/main/{fname}")
        sh(f"unzip -q -o negative_datasets/{fname} -d negative_datasets")
print("DATA READY")
