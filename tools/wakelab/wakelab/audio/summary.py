"""Metrics + human-readable rendering for an acoustic screening run (SYNTHETIC)."""
from collections import Counter, defaultdict


def _rate(rows, det):
    return (sum(r["hits"][det] for r in rows), len(rows))


def summarize(res):
    out = {}
    for d in (x["name"] for x in res["detectors"]):
        pos, neg, sk = res["positives"], res["negatives"], res["soak"]
        hit, n = _rate(pos, d)
        by_cond = {c: _rate([r for r in pos if r["condition"] == c], d) for c in res["conditions"]}
        by_style = {s: _rate([r for r in pos if r["style"] == s], d) for s in res["styles"]}
        fires = [r for r in neg if r["hits"][d]]
        fire_texts = Counter(r["text"] for r in fires)
        by_origin = defaultdict(lambda: [0, 0])
        for r in neg:
            key = r["origin"].split("+")[0].split(":")[0]
            by_origin[key][1] += 1
            by_origin[key][0] += r["hits"][d]
        soak_events = [e for e in sk["events"] if e["detector"] == d]
        out[d] = {
            "true_wake_rate": round(hit / n, 3) if n else None, "positives": [hit, n],
            "missed_wake_rate": round(1 - hit / n, 3) if n else None,
            "by_condition": {k: [a, b] for k, (a, b) in by_cond.items()},
            "by_style": {k: [a, b] for k, (a, b) in by_style.items()},
            "adversarial_false_wake_rate": round(len(fires) / len(neg), 3) if neg else None,
            "adversarial": [len(fires), len(neg)],
            "adversarial_by_origin": {k: v for k, v in sorted(by_origin.items())},
            "adversarial_fired_on": fire_texts.most_common(25),
            "soak_hours": sk["hours"], "soak_false_wakes": len(soak_events),
            "soak_false_wakes_per_hour": round(len(soak_events) / sk["hours"], 2) if sk["hours"] else None,
            "soak_fired_on": [(e["utterance"], e["transcript"][:120]) for e in soak_events[:25]],
        }
    return out


def _pct(a_b):
    a, b = a_b
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def render(res, summ):
    L = [f"ACOUSTIC SCREENING - \"{res['candidate']}\"   [{res['label']}]",
         f"TTS {res['tts_model']}; spoken: {res['spoken_texts']}; pronunciation instruction: "
         f"\"{res['pron_instruction']}\"", ""]
    dets = [d["name"] for d in res["detectors"]]
    L.append("detector".ljust(22) + "".join(d.ljust(20) for d in dets))
    rows = [("true wakes", lambda s: _pct(s["positives"])),
            ("adversarial false", lambda s: _pct(s["adversarial"])),
            ("soak false wakes", lambda s: f"{s['soak_false_wakes']} in {s['soak_hours']} h"),
            ("soak per hour", lambda s: str(s["soak_false_wakes_per_hour"]))]
    for label, fn in rows:
        L.append(label.ljust(22) + "".join(fn(summ[d]).ljust(20) for d in dets))
    L += ["", "true wakes by condition:"]
    for c in res["conditions"]:
        L.append("  " + c.ljust(20) + "".join(_pct(summ[d]["by_condition"][c]).ljust(20) for d in dets))
    L += ["true wakes by speaking style:"]
    for s in res["styles"]:
        L.append("  " + s.ljust(20) + "".join(_pct(summ[d]["by_style"][s]).ljust(20) for d in dets))
    L += ["adversarial false wakes by origin:"]
    origins = sorted({o for d in dets for o in summ[d]["adversarial_by_origin"]})
    for o in origins:
        L.append("  " + o.ljust(20) + "".join(_pct(summ[d]["adversarial_by_origin"].get(o, [0, 0])).ljust(20)
                                               for d in dets))
    for d in dets:
        s = summ[d]
        L += ["", f"[{d}] adversarial lines that woke it: " +
              (", ".join(f"\"{t}\" x{c}" for t, c in s["adversarial_fired_on"][:12]) or "none")]
        L.append(f"[{d}] soak false wakes: " +
                 ("; ".join(f"{u}: \"{t}\"" for u, t in s["soak_fired_on"][:8]) or "none"))
    L += ["", "SYNTHETIC: synthetic voices, simulated rooms, read audiobook speech for soak. "
          "Real Room 214 testing and real conversational soak are still required."]
    return "\n".join(L)
