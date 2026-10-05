"""Decode the pinned People's Speech shards to 16 kHz mono WAV (excluding any transcript that
contains 'sequoia'), then build microWakeWord features with the lab's identical seeded pipeline.
Writes manifest.json (ids, durations, sha256 of each shard, exclusions)."""
import hashlib, io, json, sys
from pathlib import Path
import numpy as np, pyarrow.parquet as pq, soundfile as sf
from scipy.signal import resample_poly
HERE = Path(__file__).resolve().parent
LAB = Path.home() / "CAOSCARE-WAKE-FUNNEL/firmware/voice-pe-aria/lab"
sys.path.insert(0, str(LAB))
SHARDS = ["clean/validation-00000-of-00005.parquet", "clean/validation-00001-of-00005.parquet"]
out = HERE / "wavs"; out.mkdir(exist_ok=True)
man = {"source": "MLCommons/peoples_speech", "revision": "f10597c5d3d3a63f8b6827701297c3afdf178272",
       "licence": "CC-BY / CC-BY-SA family (dataset card)", "shards": {}, "excluded_sequoia": [], "clips": 0, "seconds": 0.0}
for sh in SHARDS:
    man["shards"][sh] = hashlib.sha256((HERE / sh).read_bytes()).hexdigest()
    pf = pq.ParquetFile(HERE / sh)
    for rg in range(pf.num_row_groups):
        for r in pf.read_row_group(rg).to_pylist():
            if "sequoia" in (r["text"] or "").lower():
                man["excluded_sequoia"].append(r["id"]); continue
            name = hashlib.sha1(r["id"].encode()).hexdigest()[:16] + ".wav"
            f = out / name
            a, sr = sf.read(io.BytesIO(r["audio"]["bytes"]), dtype="float32")
            if a.ndim > 1: a = a.mean(axis=1)
            if sr != 16000: a = resample_poly(a, 16000, sr).astype("float32")
            if not f.exists(): sf.write(f, a, 16000, subtype="PCM_16")
            man["clips"] += 1; man["seconds"] += len(a) / 16000
man["hours"] = round(man["seconds"] / 3600, 2)
(HERE / "manifest.json").write_text(json.dumps(man, indent=1))
print({k: man[k] for k in ("clips", "hours")}, "excluded", len(man["excluded_sequoia"]), flush=True)
from train_lab import features
features(out, HERE / "features", 1)
print("FEATURES DONE", flush=True)
