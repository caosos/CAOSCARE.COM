"""Stage 1 input - run every generated candidate through the Wake Phrase Lab text screen.

For each candidate (its explicit intended phonemes) this records the lab's raw, measurable
evidence: gate results, nearest colliding words/phrases/names, collision margin, text-proxy
false-wake risk per hour, self word-frequency, speakability metrics and the names behind any
G4 (names/domain) failure. No scoring happens here; score.py turns this into the funnel.

Resumable: results/screen_raw.jsonl is appended one candidate at a time and existing ids are
skipped on restart. Read-only with respect to everything outside results/.

usage: python screen.py [workers]     (Wake Phrase Lab venv; default 3 workers)
"""
import json
import sys
from multiprocessing import get_context
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools" / "wakelab"))
from wakelab.config import settings          # noqa: E402
from wakelab.inspect import Lab               # noqa: E402
from wakelab.rank import dimensions, hostile  # noqa: E402

OUT = HERE / "results/screen_raw.jsonl"
_G = {}


def _g4_names(rep):
    names = []
    for e in rep["pronunciations"]:
        for g in e["gates"]:
            if g["gate"] == "G4_domain_names_commands" and g["result"] == "FAIL":
                names += [{"text": f["text"], "metric": f["metric"], "distance": f["distance"]}
                          for f in g["evidence"]]
    return names


def screen(c):
    lab, near = _G["lab"], _G["near"]
    rep = lab.inspect(c["text"], phonemes=c["phonemes"])
    d = dimensions(rep, near)
    sp = rep["pronunciations"][0]["speakability"]
    out = {"id": c["id"], "failed_gates": d["failed_gates"], "collision_margin": d["collision_margin"],
           "risk_per_hour": d["risk_per_hour"], "self_zipf": d["self_zipf"], "speakability": sp,
           "nearest": [{k: n[k] for k in ("text", "distance", "metric", "relation", "zipf")}
                       for n in d["nearest_neighbours"][:6]],
           "g4_evidence": _g4_names(rep)}
    if c["category"] == "aria":
        out["area_distance"] = hostile(lab, c["text"], [tuple(c["phonemes"].split())])[0]["distance"]
    return out


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    cands = json.loads((HERE / "results/candidates_generated.json").read_text())["candidates"]
    done = set()
    if OUT.exists():
        done = {json.loads(line)["id"] for line in OUT.read_text().splitlines() if line.strip()}
    todo = [c for c in cands if c["id"] not in done]
    print(f"{len(done)} already screened, {len(todo)} to go", flush=True)
    cfg = settings()
    _G["lab"], _G["near"] = Lab(cfg), cfg["distance"]["near"]   # loaded once, shared by fork
    with get_context("fork").Pool(workers) as pool, OUT.open("a") as fh:
        for i, r in enumerate(pool.imap_unordered(screen, todo, chunksize=4), 1):
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    print("SCREEN COMPLETE", flush=True)


if __name__ == "__main__":
    main()
