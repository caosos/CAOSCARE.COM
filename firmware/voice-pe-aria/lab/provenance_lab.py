"""Write results/provenance.json: a traceable record of everything behind the results.

Records:
- tool versions and commits;
- lab configuration constants;
- data sources and licences (see LICENSES.md);
- a SHA-256 digest of every sample set (sha256 over the sorted per-file hashes,
  with file counts);
- the ambient stream manifest;
- every trained model's tflite and manifest hash;
- the Phase 1 corpus manifest.

usage: provenance_lab.py   (research venv)
"""
import datetime
import hashlib
import json
import subprocess
import sys
from importlib import metadata

import lab_common as L


def set_digest(root):
    files = sorted(p for p in root.rglob("*.wav"))
    h = hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(root)).encode())
        h.update(L.sha256(p).encode())
    return {"files": len(files), "sha256_of_file_hashes": h.hexdigest()}


def timings(slug):
    """Training start = birth time of train_<slug>.log (stat %W), finish = model file mtime."""
    log = L.WORK / "lab_logs" / f"train_{slug}.log"
    tfl = L.RUNS / slug / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
    out = {"train_log": str(log) if log.exists() else None}
    if log.exists():
        born = subprocess.run(["stat", "-c", "%W", str(log)], capture_output=True, text=True).stdout.strip()
        start = int(born) if born.isdigit() and int(born) > 0 else int(log.stat().st_mtime)
        out["train_start"] = datetime.datetime.fromtimestamp(start, datetime.timezone.utc).isoformat()
        if tfl.exists():
            end = int(tfl.stat().st_mtime)
            out["train_finish"] = datetime.datetime.fromtimestamp(end, datetime.timezone.utc).isoformat()
            out["train_duration_min"] = round((end - start) / 60, 1)
        txt = log.read_text(errors="ignore").replace("\r", "\n")
        best = [x for x in txt.splitlines() if "So far the best" in x]
        out["best_checkpoint"] = best[-1].split("INFO:absl:")[-1] if best else None
        out["dipco_test_cutoffs"] = [x.split("INFO:absl:")[-1] for x in txt.splitlines()
                                     if x.startswith("INFO:absl:Cutoff ")]
    return out


def status(slug):
    tfl = L.RUNS / slug / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
    pl = (L.WORK / "lab_logs/pipeline.log")
    plog = pl.read_text() if pl.exists() else ""
    events = [x for x in plog.splitlines() if f" {slug}" in x and ("FAIL" in x or "RETRY" in x)]
    st = "evaluated" if (L.RUNS / slug / "lab_eval.json").exists() else "trained" if tfl.exists() else "FAILED"
    if any("FAILED_FINAL" in e for e in events) or st == "FAILED":
        st = "FAILED" if not (L.RUNS / slug / "lab_eval.json").exists() else st
    fails = sorted(str(p) for p in (L.WORK / "lab_logs/failures").glob(f"*_{slug}.attempt*.log")) \
        if (L.WORK / "lab_logs/failures").exists() else []
    return {"status": st, "cross_check_done": (L.RUNS / slug / "lab_eval_supp_cross.json").exists(),
            "pipeline_events": events, "failure_logs": fails}


def git(path, *args):
    try:
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def main():
    pk = {}
    for name in ("tensorflow", "microwakeword", "piper-tts", "piper-sample-generator", "torch", "numpy",
                 "pyroomacoustics", "librosa", "tflite-micro", "audiomentations", "datasets"):
        try:
            pk[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pk[name] = None
    sets = {}
    for rel in ("train/negatives", "train/positives", "eval"):
        root = L.SAMPLES / rel
        if root.exists():
            if rel == "train/positives":
                for d in sorted(root.iterdir()):
                    sets[f"{rel}/{d.name}"] = set_digest(d)
            else:
                sets[rel] = set_digest(root)
    models = {}
    for c in L.load_all_candidates():
        t = L.RUNS / c["slug"] / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
        cfgf = L.RUNS / c["slug"] / "training_parameters.yaml"
        models[c["slug"]] = {
            "id": c["id"], "group": c.get("group", "original 15"), "text": c["text"],
            "pronunciation_arpabet": c["phonemes"], "form": "launcher" if c["text"].split()[0] in
            ("hey", "hi", "hello", "okay") and len(c["text"].split()) > 1 else "bare",
            "excluded_same_sound_negatives": c.get("exclude_negatives", []),
            "tflite": str(t) if t.exists() else None, "sha256": L.sha256(t) if t.exists() else None,
            "bytes": t.stat().st_size if t.exists() else None,
            "training_parameters_sha256": L.sha256(cfgf) if cfgf.exists() else None,
            "licensing": "RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE", "commercial_release_eligible": False,
            **status(c["slug"]), **timings(c["slug"])}
    streams = json.loads((L.EVAL_DATA / "streams/streams_manifest.json").read_text())
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python": sys.version.split()[0], "packages": pk,
        "commits": {"caoscare_branch": git(L.LAB, "rev-parse", "HEAD"),
                    "microWakeWord": git(L.WORK / "microWakeWord", "rev-parse", "HEAD"),
                    "microWakeWord_local_patch": git(L.WORK / "microWakeWord", "diff", "--stat"),
                    "piper-sample-generator": git(L.WORK / "piper-sample-generator", "rev-parse", "HEAD")},
        "config": {k: getattr(L, k) for k in ("SEED", "TRAIN_POSITIVES_PER_FORM", "TRAIN_NEGATIVES_PER_PHRASE",
                                               "TRAIN_STEPS", "LENGTH_SCALES", "NOISE_SCALES", "NOISE_WS",
                                               "EVAL_LENGTH_SCALES", "CUTOFFS", "REPORT_CUTOFF")},
        "generator": {"path": str(L.GEN_PT), "sha256": L.sha256(L.GEN_PT)},
        "eval_voices": {p.name: L.sha256(p) for p in sorted(L.VOICES.glob("*.onnx"))},
        "eval_speakers": L.EVAL_SPEAKERS,
        "sample_sets": sets, "ambient_streams": streams, "models": models,
        "training_data_licences": "see LICENSES.md - all models research-only",
    }
    (L.LAB / "results/provenance.json").write_text(json.dumps(out, indent=1, default=str))
    (L.LAB / "results/model_status.json").write_text(json.dumps(
        {k: {x: v[x] for x in ("id", "group", "form", "status", "cross_check_done", "sha256",
                               "training_parameters_sha256", "train_start", "train_finish",
                               "train_duration_min", "pipeline_events", "failure_logs", "licensing") if x in v}
         for k, v in models.items()}, indent=1))
    print("models", len(models), "sets", len(sets))


if __name__ == "__main__":
    main()
