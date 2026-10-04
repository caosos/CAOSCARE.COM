"""Summarise runs/<run>/heldout_eval.json at one cutoff.

usage: summarize_eval.py <run_name> <cutoff>   (run from the training work dir)
"""
import json, sys
from collections import defaultdict
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))  # gen_samples.py beside this file
import gen_samples as G
run, cut = sys.argv[1], float(sys.argv[2])
r = json.load(open(f"runs/{run}/heldout_eval.json"))
trained = {G.slug(t) for t in G.ADVERSARIAL}
def cnt(c, key, pred=lambda sub: True):
    v = [s for sub, l in r["scores"][c][key].items() if pred(sub.split("__")[0]) for s in l]
    return f"{sum(s > cut for s in v)}/{len(v)}"
print(f"== {run} cutoff {cut}")
print(f"{'condition':20s} {'true acc':>9s} {'other ph':>9s} {'AIR-ee-uh':>9s} {'FA held-out':>11s} {'FA trained':>10s} {'FA sentence':>11s}")
for c in r["conditions"]:
    print(f"{c:20s} {cnt(c,'positives'):>9s} {cnt(c,'other_phrase'):>9s} {cnt(c,'air_ee_uh'):>9s} "
          f"{cnt(c,'adversarial',lambda p: p not in trained):>11s} {cnt(c,'adversarial',lambda p: p in trained):>10s} {cnt(c,'sentences'):>11s}")
agg = defaultdict(lambda: [0, 0])
for c in r["conditions"]:
    for key in ("adversarial", "sentences"):
        for sub, v in r["scores"][c][key].items():
            ph = sub.split("__")[0]; agg[ph][0] += sum(s > cut for s in v); agg[ph][1] += len(v)
top = sorted(((a / n, a, n, k) for k, (a, n) in agg.items() if a), reverse=True)[:12]
print("worst phrases (FA/clips, all conditions):", "; ".join(f"{k} {a}/{n}" for _, a, n, k in top))
pv = defaultdict(lambda: [0, 0])
for sub, v in r["scores"]["clean"]["positives"].items():
    voice = sub.split("__")[1]; pv[voice][0] += sum(s > cut for s in v); pv[voice][1] += len(v)
print("clean true accept by voice:", ", ".join(f"{k} {a}/{n}" for k, (a, n) in sorted(pv.items())))
