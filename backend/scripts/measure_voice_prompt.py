"""Measure what the voice bridge sends to the language model - no model call.

Builds the exact first model request of a bridge turn (system instructions +
the bridge's channel note, this session's history, the bridge tool schemas)
the way routes/voice_bridge.py does, splits the instructions into their
"## " sections, and reports characters and estimated tokens per section,
per tool and in total. Tokens are ESTIMATES (characters / 4; no tokenizer is
installed) - good for comparing sections, not for billing.

    cd backend
    .venv/bin/python scripts/measure_voice_prompt.py                # representative synthetic resident
    .venv/bin/python scripts/measure_voice_prompt.py --profile new  # resident with nothing on file
    .venv/bin/python scripts/measure_voice_prompt.py --db-resident res_xxx [--room 214]
        # read-only against the configured database; prints sizes only, never content
    --json out.json     machine-readable result

Synthetic runs use a throwaway caos_prompt_measure_* database, dropped after.
"""
import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# heading prefix -> (source, inclusion, classification)
# inclusion: always | per-resident | when-present
# classification: always | by-intent | after-tool | on-demand | summary | duplication
SECTIONS = [
    ("## About yourself", ("realtime_self_knowledge._system_self_knowledge", "always", "on-demand")),
    ("## What you actually run on", ("realtime_self_knowledge._system_self_knowledge", "always", "on-demand")),
    ("## What's on the kiosk screen", ("realtime_self_knowledge._system_self_knowledge", "always", "on-demand")),
    ("## What you can DO right now", ("realtime_self_knowledge._system_self_knowledge", "always", "duplication")),
    ("## What you can do", ("companion_tool_guidance.render_capabilities", "always", "always")),
    ("## NEVER over-promise", ("realtime_self_knowledge._system_self_knowledge", "always", "duplication")),
    ("## Right now", ("realtime_companion_prompt time anchor (_facility_now)", "always", "always")),
    ("## Who you are", ("realtime_companion_prompt persona", "always", "always")),
    ("## How you sound", ("realtime_companion_prompt persona", "always", "always")),
    ("## Language", ("realtime_companion_prompt persona", "always", "always")),
    ("## What never to say", ("realtime_companion_prompt persona", "always", "always")),
    ("## What to do", ("realtime_companion_prompt persona", "always", "always")),
    ("## Visually impaired", ("realtime_companion_prompt persona", "always", "always")),
    ("## Truth discipline", ("realtime_companion_prompt governance", "always", "always")),
    ("## Memory is reference", ("realtime_companion_prompt governance", "always", "always")),
    ("## Attribution discipline", ("realtime_companion_prompt governance", "always", "always")),
    ("## When you make a mistake", ("realtime_companion_prompt governance", "always", "always")),
    ("## Tools you can actually use", ("companion_tool_guidance.render_tool_guidance", "always", "by-intent")),
    ("## How to be more than Alexa", ("realtime_companion_prompt persona", "always", "by-intent")),
    ("## Sensitive adult-life topics", ("realtime_companion_prompt persona", "always", "by-intent")),
    ("## Safety", ("realtime_companion_prompt safety", "always", "always")),
    ("## About this person", ("realtime_companion_memory profile + intake notes", "per-resident", "always")),
    ("## What you know about", ("realtime_companion_memory facts bin (<=40)", "per-resident", "on-demand")),
    ("## Recent moments with", ("realtime_companion_memory events bin (<=20)", "per-resident", "on-demand")),
    ("## What you've learned about how", ("aria_interpretation_patterns.render_interpretation_block", "when-present", "always")),
    ("## Where you and", ("aria_continuity.render_continuity_block (Layer B)", "when-present", "summary")),
    ("## This call so far", ("aria_conversation_state (Layer C)", "when-present", "always")),
    ("## What's actually happening right now", ("realtime_operational_context (Layer E)", "when-present", "always")),
    ("## This conversation's channel", ("voice_bridge.CHANNEL_NOTE", "always", "always")),
]


def est_tokens(chars: int) -> int:
    return round(chars / 4)


def classify(heading: str):
    for prefix, meta in SECTIONS:
        if heading.startswith(prefix):
            return meta
    return ("unmapped", "?", "?")


def split_sections(text: str) -> list:
    parts, cur_head, cur = [], "(preamble)", []
    for line in text.splitlines(keepends=True):
        if line.startswith("## ") or (line.startswith("# ") and not cur):
            if cur:
                parts.append((cur_head, "".join(cur)))
            cur_head, cur = line.strip(), [line]
        else:
            cur.append(line)
    if cur:
        parts.append((cur_head, "".join(cur)))
    return parts


async def seed_synthetic(db, profile: str) -> dict:
    from datetime import datetime, timedelta, timezone
    from routes.departments import seed_default_departments
    await seed_default_departments()
    now = datetime.now(timezone.utc)
    rid, room, sid = "res_measure", "M-101", "vb_measure-current"
    doc = {"resident_id": rid, "name": "Margaret Ellen Hughes", "preferred_name": "Maggie", "room": room}
    if profile == "representative":
        doc.update(low_vision=True,
                   preferences="gardening, old westerns, lemon cake, her two cats, gospel music on Sunday mornings",
                   memory="Retired school librarian from Little Rock. Two daughters (Carol, Denise), four grandchildren. "
                          "Husband Frank passed in 2019. Hearing aid in left ear.")
    await db.residents.insert_one(doc)
    if profile != "representative":
        return {"resident_id": rid, "room": room, "session_id": sid, "history_turns": 0}
    facts = [f"Maggie's daughter {n} visits on {d}." for n, d in (("Carol", "Sundays"), ("Denise", "Wednesdays"))]
    facts += [f"Maggie prefers {x}." for x in ("tea with honey in the evening", "the window blinds half open",
                                              "being called Maggie, never Margaret", "decaf after 3 PM",
                                              "short walks to the garden courtyard", "classic country on the radio")]
    facts += [f"Maggie has a cat named {c} that her daughter cares for." for c in ("Biscuit", "Pepper")]
    facts += [f"Fact {i}: Maggie mentioned a detail about her life, family or routine worth remembering."
              for i in range(17)]
    await db.memories.insert_many([{"memory_id": uuid.uuid4().hex, "resident_id": rid, "bin": "facts", "text": t,
                                    "importance": 3, "pinned": i < 2, "created_at": now.isoformat()}
                                   for i, t in enumerate(facts)])
    await db.memories.insert_many([{"memory_id": uuid.uuid4().hex, "resident_id": rid, "bin": "events",
                                    "text": f"Talked about {t}.", "event_at": (now - timedelta(days=i)).isoformat(),
                                    "created_at": now.isoformat()}
                                   for i, t in enumerate(["her granddaughter's recital", "the garden tomatoes",
                                                          "feeling tired after physical therapy", "a western movie",
                                                          "the church choir", "her late husband's birthday",
                                                          "new shoes", "the weather turning cool"])])
    await db.alerts.insert_one({"alert_id": "alert_measure", "resident_id": rid, "room": room, "status": "acknowledged",
                                "severity": "assist", "created_at": (now - timedelta(minutes=12)).isoformat(),
                                "acknowledged_by_name": "Nurse Ana", "press_count": 1})
    await db.staff_tasks.insert_many([
        {"task_id": f"task_m{i}", "resident_id": rid, "room": room, "category": c, "status": "pending",
         "title": t, "resident_words": t, "created_at": (now - timedelta(hours=i + 1)).isoformat(),
         "conversation_session_id": "vb_measure-old"}
        for i, (c, t) in enumerate([("maintenance", "My bathroom sink is dripping"),
                                    ("housekeeping", "Could I get fresh towels")])])
    for k, sess in enumerate(("vb_measure-old", "vb_measure-older")):
        for j in range(10):
            await db.conversations.insert_one({
                "resident_id": rid, "session_id": sess, "role": "user" if j % 2 == 0 else "assistant",
                "content": ("My bathroom sink is dripping again, it kept me up." if j % 2 == 0 else
                            "I'm sorry, Maggie. I've passed that to maintenance; no one has picked it up yet."),
                "created_at": (now - timedelta(hours=k + 1, minutes=10 - j)).isoformat(), "room": room})
        await db.realtime_diagnostics.insert_one({"session_id": sess, "event_type": "session_ended",
                                                  "meta": {"reason": "resident_phrase"},
                                                  "created_at": (now - timedelta(hours=k + 1)).isoformat()})
    for j in range(8):
        await db.conversations.insert_one({
            "resident_id": rid, "session_id": sid, "role": "user" if j % 2 == 0 else "assistant",
            "content": ("What's for dinner tonight? And is there anything fun this afternoon?" if j % 2 == 0 else
                        "Tonight it's roast chicken with green beans, and there's chair yoga at two."),
            "created_at": (now - timedelta(minutes=8 - j)).isoformat(), "room": room})
    for heard, meant in (("dos savor", "dos sabores (two flavors)"), ("the clicker", "the TV remote"),
                         ("my Sunday girl", "her daughter Carol")):
        await db.interpretation_patterns.insert_one({"resident_id": rid, "heard_as": heard, "heard_norm": heard,
                                                     "understood_as": meant, "confirmed_count": 2,
                                                     "last_confirmed_at": now.isoformat()})
    return {"resident_id": rid, "room": room, "session_id": sid, "history_turns": 8}


async def measure(resident_id, room, session_id) -> dict:
    from routes.resident_conversation_context import build_resident_instructions
    from routes.voice_bridge import CHANNEL_NOTE, HISTORY_TURNS, _history
    from routes.voice_bridge_tools import bridge_tool_schemas
    from routes.realtime_tools import _build_tools
    tools = await bridge_tool_schemas()
    names = tuple(t["function"]["name"] for t in tools)
    payload = {"resident_id": resident_id, "room": room, "session_id": session_id}
    try:  # mirrors voice_bridge._converse
        built = await build_resident_instructions(payload, tools=names, channel="voice")
    except TypeError:  # builds before Phase A took no tool list
        built = await build_resident_instructions(payload)
    system = built["instructions"] + CHANNEL_NOTE
    history = await _history(session_id)
    contract = _contract(system, names, {t["name"] for t in await _build_tools()})
    sections = []
    for head, body in split_sections(system):
        src, inc, cls = classify(head)
        sections.append({"section": head[:70], "source": src, "inclusion": inc, "classification": cls,
                         "chars": len(body), "est_tokens": est_tokens(len(body))})
    tool_rows = [{"tool": t["function"]["name"], "chars": len(json.dumps(t)),
                  "est_tokens": est_tokens(len(json.dumps(t)))} for t in tools]
    hist_chars = sum(len(m["content"]) for m in history)
    tools_chars = len(json.dumps(tools))
    total = len(system) + hist_chars + tools_chars
    return {
        "identifiers": {"resident_id": resident_id, "room": room, "session_id": session_id},
        "system_chars": len(system), "history": {"messages": len(history), "chars": hist_chars,
                                                 "cap_messages": HISTORY_TURNS},
        "tools": {"count": len(tools), "chars": tools_chars, "per_tool": tool_rows},
        "contract": contract,
        "sections": sections,
        "total_chars": total, "total_est_tokens": est_tokens(total),
        "layers_present": {k: built.get(k) is not None and built.get(k) != [] for k in
                           ("op_state", "continuity", "conv_state", "interpretation_patterns")},
        "omitted": {"menu/activities data": "not in the prompt; fetched by get_menu / get_todays_schedule tools",
                    "receipts and provenance": "not in the prompt; written server-side by the bridge",
                    "department list": "not in the prompt; inside the request_staff_help tool schema"},
    }


def _contract(system: str, provided, universe) -> dict:
    from routes import companion_prompt_contract as c
    return {
        "tools_exposed": list(provided),
        "unsupported_tool_claims": c.unsupported_tool_claims(system, provided, universe),
        "unsupported_capability_claims": c.unsupported_capability_claims(system, provided, "voice"),
        "rule_counts": c.rule_counts(system),
        "duplicated_instructions": c.duplicated_instructions(system),
        "required_sections_missing": c.missing_sections(system),
    }


def render(r: dict) -> str:
    out = [f"total {r['total_chars']} chars (~{r['total_est_tokens']} tokens est.): system {r['system_chars']}, "
           f"history {r['history']['chars']} ({r['history']['messages']} msgs), tools {r['tools']['chars']} "
           f"({r['tools']['count']} tools)", "", "| section | source | inclusion | class | chars | ~tokens |",
           "|---|---|---|---|---|---|"]
    for s in r["sections"]:
        out.append(f"| {s['section']} | {s['source']} | {s['inclusion']} | {s['classification']} | "
                   f"{s['chars']} | {s['est_tokens']} |")
    out += ["", "| tool | chars | ~tokens |", "|---|---|---|"]
    out += [f"| {t['tool']} | {t['chars']} | {t['est_tokens']} |" for t in r["tools"]["per_tool"]]
    k = r["contract"]
    out += ["", f"tools exposed: {', '.join(k['tools_exposed'])}",
            f"unsupported tool claims: {k['unsupported_tool_claims'] or 'none'}",
            f"unsupported capability claims: {k['unsupported_capability_claims'] or 'none'}",
            f"duplicated instructions: {len(k['duplicated_instructions'])} {k['duplicated_instructions']}",
            f"required sections missing: {k['required_sections_missing'] or 'none'}"]
    return "\n".join(out)


async def main(args):
    if args.db_resident:
        from deps import db
        res = await db.residents.find_one({"resident_id": args.db_resident}, {"_id": 0, "room": 1})
        if not res:
            sys.exit("resident not found")
        last = await db.conversations.find_one({"resident_id": args.db_resident}, {"session_id": 1},
                                               sort=[("created_at", -1)])
        r = await measure(args.db_resident, args.room or res.get("room"), (last or {}).get("session_id") or "none")
        r["identifiers"]["note"] = "configured database, read-only; content not printed"
    else:
        os.environ["DB_NAME"] = f"caos_prompt_measure_{uuid.uuid4().hex[:8]}"
        os.environ["OPENAI_API_KEY"] = ""
        from deps import db
        try:
            ids = await seed_synthetic(db, args.profile)
            r = await measure(ids["resident_id"], ids["room"], ids["session_id"])
            r["identifiers"]["profile"] = args.profile
        finally:
            await db.client.drop_database(os.environ["DB_NAME"])
    print(render(r))
    if args.json:
        Path(args.json).write_text(json.dumps(r, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--profile", choices=("representative", "new"), default="representative")
    p.add_argument("--db-resident")
    p.add_argument("--room")
    p.add_argument("--json")
    asyncio.run(main(p.parse_args()))
