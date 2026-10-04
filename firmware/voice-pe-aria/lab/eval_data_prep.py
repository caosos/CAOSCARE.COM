"""Build the fixed evaluation noise/ambient material (identical for all models).

Outputs (16 kHz mono int16 WAV) under ~/caoscare-firmware-work/eval_data/streams
plus streams_manifest.json (source, license, duration, sha256):

  tv_dialogue   LibriSpeech test-clean, speakers in the first half (sorted id),
                concatenated - a television/radio *dialogue proxy* (read speech).
  talker_pool   LibriSpeech test-clean, speakers in the second half - used to
                mix "TV on" / "other person talking" into clips (never overlaps
                tv_dialogue speakers).
  music         Free Music Archive (fma_small, HF benjamin-paine/free-music-archive-small
                shard 14), tracks NOT in the training background set (fma_16k),
                only tracks flagged allow_commercial_use=1 and allow_derivatives=1;
                per-track metadata recorded.
  background    DEMAND (Thiemann et al., CC BY-SA 3.0) DLIVING, DKITCHEN,
                OMEETING, PCAFETER channel 1.
  hvac          procedural HVAC (brown + pink noise, 60/120 Hz hum, blade tone,
                slow modulation) - synthetic, generated here, seeded.
  silence       digital near-silence (-80 dBFS white noise floor), seeded.
"""
import io
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter, resample_poly

from lab_common import EVAL_DATA, SEED, WORK, sha256

SR = 16000
OUT = EVAL_DATA / "streams"
LIBRI = Path.home() / ".cache/caoscare-wakelab/librispeech_test_clean/LibriSpeech/test-clean"
DURATION_S = {"tv_dialogue": 3 * 3600, "music": 3600, "background": 1800, "hvac": 3600, "silence": 1800,
              "talker_pool": 1800}


def to16k(a, sr):
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        from math import gcd
        g = gcd(sr, SR)
        a = resample_poly(a, SR // g, sr // g)
    return a.astype(np.float32)


def write(name, a, meta):
    OUT.mkdir(parents=True, exist_ok=True)
    a = a / max(1e-9, np.abs(a).max()) * 0.5 if name != "silence" else a
    pcm = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    p = OUT / f"{name}.wav"
    sf.write(p, pcm, SR, subtype="PCM_16")
    meta.update({"file": p.name, "seconds": round(len(pcm) / SR, 1), "sha256": sha256(p)})
    return meta


def libri(first_half):
    spk = sorted(d.name for d in LIBRI.iterdir() if d.is_dir())
    half = spk[: len(spk) // 2] if first_half else spk[len(spk) // 2:]
    want = DURATION_S["tv_dialogue" if first_half else "talker_pool"] * SR
    parts, n = [], 0
    for s in half:
        for f in sorted((LIBRI / s).rglob("*.flac")):
            a, sr = sf.read(f)
            a = to16k(a, sr)
            parts += [a, np.zeros(int(0.3 * SR), np.float32)]
            n += len(a)
            if n >= want:
                return np.concatenate(parts)[:want], half
    return np.concatenate(parts), half


def music():
    """Tracks with allow_commercial_use=1 and allow_derivatives=1 only; id from the audio path."""
    import pyarrow.parquet as pq
    train_ids = {int(p.stem) for p in (WORK / "data/fma_16k").glob("*.wav") if p.stem.isdigit()}
    t = pq.read_table(EVAL_DATA / "fma_small_shard14.parquet")
    parts, n, tracks = [], 0, []
    for i in range(t.num_rows):
        if not (t.column("allow_commercial_use")[i].as_py() and t.column("allow_derivatives")[i].as_py()):
            continue
        aud = t.column("audio")[i].as_py()
        tid = int(Path(aud["path"]).stem)
        if tid in train_ids:
            continue
        try:
            a, sr = sf.read(io.BytesIO(aud["bytes"]))
        except Exception:
            continue
        parts.append(to16k(a, sr))
        tracks.append({"track_id": tid, "license_code": t.column("license")[i].as_py(),
                       "title": t.column("title")[i].as_py(), "artist": t.column("artist")[i].as_py(),
                       "url": t.column("url")[i].as_py()})
        n += len(parts[-1])
        if n >= DURATION_S["music"] * SR:
            break
    return np.concatenate(parts)[: DURATION_S["music"] * SR], tracks


def demand():
    parts = []
    for env in ("DLIVING", "DKITCHEN", "OMEETING", "PCAFETER"):
        f = next((EVAL_DATA / "demand" / env).glob("ch01.wav"))
        a, sr = sf.read(f)
        parts.append(to16k(a, sr))
    return np.concatenate(parts)[: DURATION_S["background"] * SR]


def hvac():
    rng = np.random.default_rng(SEED)
    n = DURATION_S["hvac"] * SR
    t = np.arange(n) / SR
    brown = np.cumsum(rng.standard_normal(n))
    brown = lfilter(*butter(2, 20 / (SR / 2), "high"), brown)
    pink = lfilter(*butter(1, 1500 / (SR / 2)), rng.standard_normal(n))
    hum = 0.3 * np.sin(2 * np.pi * 60 * t) + 0.2 * np.sin(2 * np.pi * 120 * t)
    blade = 0.15 * np.sin(2 * np.pi * 147 * t) * (1 + 0.3 * np.sin(2 * np.pi * 0.25 * t))
    mod = 1 + 0.2 * np.sin(2 * np.pi * 0.05 * t)
    a = (brown / np.abs(brown).max() + 0.6 * pink / np.abs(pink).max() + hum + blade) * mod
    return a.astype(np.float32)


def main():
    meta = {}
    a, spk = libri(True)
    meta["tv_dialogue"] = write("tv_dialogue", a, {"source": "LibriSpeech test-clean (openslr 12)",
                                                    "license": "CC BY 4.0", "speakers": spk,
                                                    "note": "television dialogue PROXY - read audiobook speech"})
    a, spk = libri(False)
    meta["talker_pool"] = write("talker_pool", a, {"source": "LibriSpeech test-clean (openslr 12)",
                                                    "license": "CC BY 4.0", "speakers": spk})
    a, tracks = music()
    meta["music"] = write("music", a, {"source": "Free Music Archive fma_small via HF benjamin-paine/"
                                                  "free-music-archive-small shard 14",
                                        "license": "per track; only allow_commercial_use=1 and allow_derivatives=1 kept (codes per dataset card)", "tracks": tracks})
    meta["background"] = write("background", demand(), {"source": "DEMAND (zenodo 1227121) ch01 of DLIVING, "
                                                                  "DKITCHEN, OMEETING, PCAFETER",
                                                        "license": "CC BY-SA 3.0"})
    meta["hvac"] = write("hvac", hvac(), {"source": "procedural (eval_data_prep.py, seed)", "license": "generated"})
    rng = np.random.default_rng(SEED + 1)
    meta["silence"] = write("silence", (rng.standard_normal(DURATION_S["silence"] * SR) * 1e-4).astype(np.float32),
                            {"source": "procedural near-silence (-80 dBFS)", "license": "generated"})
    (OUT / "streams_manifest.json").write_text(json.dumps(meta, indent=1))
    print({k: v["seconds"] for k, v in meta.items()})


if __name__ == "__main__":
    main()
