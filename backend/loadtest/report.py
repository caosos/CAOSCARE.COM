"""Markdown tables from loadtest/results/*.json (python -m loadtest.report)."""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent / "results"


def bar(v, scale, width=30):
    return "█" * max(0, min(width, round((v or 0) / scale * width)))


def level_table(f):
    d = json.loads((R / f).read_text())
    c = d["config"]
    out = [f"**{f}** — workers {c['workers']}, model slots/worker {c['max_active']} "
           f"(reserved {c['reserved']}), simulated model {c['llm_ms']}±{c['llm_jitter_ms']} ms\n",
           "| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped "
           "| app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, l in d["levels"].items():
        a, r, k = l["first_ack_s"], l["resources"], l["checks"]
        dup = len(k["duplicate_open_requests"]) + len(k["duplicate_open_help_events"])
        out.append(f"| {n} | {l['turns']} | {l['throughput_turns_per_s']} | {a['p50']}/{a['p95']}/{a['max']} | "
                   f"{l['complete_response_s']['p95']} | {l['deferred_turns']} | {l['degraded_turns']} | "
                   f"{l['dropped_turns']} | {r['app_cpu_pct']['p95']} | {r['mongo_cpu_pct']['p95']} | "
                   f"{r['host_cpu_pct']['p95']} | {round(r['rss_mb']['max'])} | {r['conns']['max']} | "
                   f"{k['missing_receipts']}/{k['orphan_receipts'] + len(k['orphan_tasks']) + len(k['orphan_help_events'])} | "
                   f"{l['client_leaks'] + l['server']['leak_contexts']} | {dup} | {k['ending_succeeded']}/{k['ending_requested']} |")
    out.append("")
    out.append("```")
    out.append("first-answer p95 (s)")
    for n, l in d["levels"].items():
        out.append(f"{n:>4} rooms {bar(l['first_ack_s']['p95'], 10)} {l['first_ack_s']['p95']}")
    out.append("backend CPU p95 (% of one core)")
    for n, l in d["levels"].items():
        v = l["resources"]["app_cpu_pct"]["p95"]
        out.append(f"{n:>4} rooms {bar(v, 400)} {v}")
    out.append("```\n")
    return "\n".join(out)


def class_table(f):
    d = json.loads((R / f).read_text())
    out = [f"**{f}** — per priority class (turns / deferred / degraded / first-answer p95 s)\n",
           "| rooms | " + " | ".join(["emergency", "staff_help", "operational", "room_action", "information",
                                     "conversation", "session_end", "retry"]) + " |",
           "|---" * 9 + "|"]
    for n, l in d["levels"].items():
        cells = []
        for c in ["emergency", "staff_help", "operational", "room_action", "information", "conversation",
                  "session_end", "retry"]:
            v = l["by_class"].get(c)
            cells.append(f"{v['turns']}/{v['deferred']}/{v['degraded']}/{v['p95_s']}" if v else "-")
        out.append(f"| {n} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(level_table(f))
        print(class_table(f))
