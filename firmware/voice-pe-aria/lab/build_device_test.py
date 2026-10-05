"""Build the RESEARCH firmware config for the three physical-test finalists.

- copies each finalist's model to device_test/models/ (gitignored: research-only weights stay out of git)
  and writes its ESPHome v2 manifest with the model's matched-point cutoff and a 1.3x arena margin;
- writes device_test/finalists-voice-pe.yaml from ../caoscare-voice-pe.yaml (same pinned official
  26.9.0 package, same removals) with the three finalists as the only wake words, first = default;
- compiles it with ESPHome 2026.9.0 and records sizes and SHA-256 in results/device_test_build.json.
RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE. Not shipping firmware. Never flashed by this script.

usage: build_device_test.py                      the three recommended finalists (original build)
       build_device_test.py <set> <slug> [...]   a named research set in device_test/<set>/ with
                                                 results/device_test_<set>.json (never overwrites the
                                                 original build); first slug = enabled on first boot
(run with the research venv; calls venv-esphome for the compile)
"""
import sys
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from lab_common import LAB, RUNS, WORK, load_all_candidates, sha256

DT = LAB / "device_test"
FW = LAB.parent
ESPHOME = WORK / "venv-esphome/bin/esphome"


def main(set_name=None, slugs=None):
    rec = json.loads((LAB / "results/recommendation.json").read_text())
    p2 = json.loads((LAB / "results/phase2_results.json").read_text())["models"]
    by_id = {c["id"]: c for c in load_all_candidates()}
    by_slug = {c["slug"]: c for c in load_all_candidates()}
    dt = DT / set_name if set_name else DT
    chosen = [by_slug[s] for s in slugs] if slugs else [by_id[i] for i in rec["physical_test_three"]]
    (dt / "models").mkdir(parents=True, exist_ok=True)
    entries, info = [], []
    for c in chosen:
        fid = c["id"]
        m = p2[c["slug"]]
        src = RUNS / c["slug"] / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
        mid = re.sub(r"[^a-z0-9]+", "_", c["slug"])[:40]
        shutil.copyfile(src, dt / "models" / f"{mid}.tflite")
        arena = int(math.ceil((m["arena_bytes"] or 25584) * 1.3 / 1000) * 1000)
        manifest = {"type": "micro", "wake_word": c["text"].title(), "author": "CAOSCare Wake Word Lab (research)",
                    "website": "https://github.com/kahrendt/microWakeWord", "model": f"{mid}.tflite",
                    "trained_languages": ["en"], "version": 2,
                    "micro": {"probability_cutoff": m["matched_cutoff"], "feature_step_size": 10,
                              "sliding_window_size": 5, "tensor_arena_size": arena,
                              "minimum_esphome_version": "2024.7.0"}}
        (dt / "models" / f"{mid}.json").write_text(json.dumps(manifest, indent=2) + "\n")
        entries.append(f"        - model: models/{mid}.json\n          id: {mid}\n")
        info.append({"id": fid, "model_id": mid, "tflite_sha256": sha256(src), "cutoff": m["matched_cutoff"],
                     "arena": arena, "manifest_sha256": sha256(dt / "models" / f"{mid}.json")})
    base = (FW / "caoscare-voice-pe.yaml").read_text()
    models_block = re.search(r"      models:\n(?:        .*\n)+?\n", base).group(0)
    new_block = ("      models:\n        # Physical-test research models (research only); first = enabled on first boot.\n"
                 + "".join(entries) + "\n")
    yml = base.replace(models_block, new_block)
    levels = [("Slightly sensitive", 0.0), ("Moderately sensitive", 0.10), ("Very sensitive", 0.20)]
    branches = []
    for i, (label, drop) in enumerate(levels):
        sets = "".join(f"          id({f['model_id']}).set_probability_cutoff("
                       f"{int(round(max(0.05, f['cutoff'] - drop) * 255))});  // {max(0.05, f['cutoff'] - drop):.2f}\n"
                       for f in info)
        branches.append(f"        {'if' if i == 0 else '} else if'} (x == \"{label}\") {{\n{sets}")
    select = ("select:\n  - id: !remove wake_word_sensitivity\n  - platform: template\n"
              "    name: \"Wake word sensitivity\"\n    id: caoscare_wake_word_sensitivity\n    optimistic: true\n"
              "    initial_option: Slightly sensitive\n    restore_value: true\n    entity_category: config\n"
              "    options:\n      - Slightly sensitive\n      - Moderately sensitive\n      - Very sensitive\n"
              "    on_value:\n      # Slightly = each model's matched-point cutoff; -0.10 / -0.20 for the others\n"
              "      lambda: |-\n" + "".join(branches) + "        }\n\n")
    yml = re.sub(r"(# The stock sensitivity select.*?\n)select:\n.*?\n\n(# The official factory firmware)",
                 lambda mo: mo.group(1) + select + mo.group(2), yml, flags=re.S)
    yml = yml.replace("name: CAOSCare.Voice PE Aria spike", "name: CAOSCare.Voice PE wake-word finalists (research)")
    yml = yml.replace("version: 26.9.0-aria.1", f"version: 26.9.0-lab.{set_name}" if set_name else "version: 26.9.0-lab.1")
    yml = "# RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE. Wake Word Lab physical-test build. Not shipping firmware.\n" + yml
    yname = f"{set_name}-voice-pe.yaml" if set_name else "finalists-voice-pe.yaml"
    (dt / yname).write_text(yml)
    r = subprocess.run([str(ESPHOME), "compile", yname], cwd=dt, capture_output=True, text=True)
    (WORK / f"lab_logs/device_test_{set_name or 'finalists'}_compile.log").write_text(r.stdout + r.stderr)
    build = dt / ".esphome/build/home-assistant-voice/build"
    out = {"finalists": info, "compile_exit": r.returncode,
           "ram_line": next((x for x in r.stdout.splitlines() if "RAM:" in x), None),
           "flash_line": next((x for x in r.stdout.splitlines() if "Flash:" in x), None),
           "licensing": "RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE"}
    for b in ("firmware.factory.bin", "firmware.ota.bin"):
        if (build / b).exists():
            out[b] = {"bytes": (build / b).stat().st_size, "sha256": sha256(build / b)}
    out["set"] = set_name or "finalists"
    out["yaml"] = str((dt / yname).relative_to(LAB))
    (LAB / (f"results/device_test_{set_name}.json" if set_name else "results/device_test_build.json")).write_text(
        json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:]) if len(sys.argv) > 2 else main()
