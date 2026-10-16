#!/usr/bin/env python3
"""GitHub side of the coordination watch: read comments through `gh` (free), classify them,
post deduplicated receipts. No model, no secrets, no transcript content - only comment
headers, URLs, states and SHAs are ever republished.

Markers:
  MAIN   <!-- claude-caoscare-session -->      Main Claude's own receipts
  WATCH  <!-- caoscare-coordination-watch -->  this watcher
  DA     <!-- desktop-agent-intake -->         Desktop-Agent deliveries
  RECV   <!-- caos:coordinator -->             receiver.py ACK/WORKING/DONE lines

Wake semantics (the established intake): Main Claude's own GitHub watch wakes on a new
comment by the owner login on the authoritative issue that does NOT carry MAIN. So a
DELIVERY comment carries WATCH only (it must wake Main Claude); a routine mirror receipt
carries WATCH+MAIN (it must not).
"""
import json
import re
import subprocess
from datetime import datetime, timezone

MAIN = "<!-- claude-caoscare-session -->"
WATCH = "<!-- caoscare-coordination-watch -->"
DA = "<!-- desktop-agent-intake -->"
RECV = "<!-- caos:coordinator -->"
STATE_RX = [
    ("BLOCKED", re.compile(r"\b(BLOCKED|NEED[ _-]?(SERVICE|ACCESS|PERMISSION|HOST_ACTION|OWNER)?|FAILED|FAILURE)\b")),
    ("DONE", re.compile(r"\b(DONE|COMPLETE[D]?|ACCEPTED|CUTOVER RECEIPT|PASSED|LIVE[- ]ACCEPTED|DEPLOYED)\b")),
    ("ACK", re.compile(r"\bACK\b")),
    ("WORKING", re.compile(r"\b(WORKING|IN PROGRESS|STARTED)\b")),
    ("RECEIPT", re.compile(r"\bRECEIPT\b")),
]
LEAD_RX = re.compile(r"^[\W_]*(ACK|WORKING|DONE|BLOCKED)\b")
BOUNDARY_RX = re.compile(r"\b(LINODE|PRODUCTION|RELEASE|DEPLOY(ED|MENT)?)\b")
BOUNDARY_DONE_RX = re.compile(r"\b(RECEIPT|DONE|DEPLOYED|COMPLETE[D]?|ACCEPTED)\b")
NEGATED_RX = re.compile(r"\b(NOT|NO|NEVER|UN)[ -]?(YET[ -])?(DEPLOYED|RELEASED|DONE|COMPLETE[D]?|ACCEPTED|LIVE|LOADED|MERGED)\b")
# Queue item ids: <lane>-<words...>-NNN (careops-153-drilldown-truth-002, public-162-site-redesign-001),
# plus coord-*, Desktop-Agent da-<hex> and CO-NNN. A missing lane here silently drops ACK/DONE (2026-10-16).
ITEM_RX = re.compile(r"\b(da-[0-9a-f]{10}|coord-[a-z0-9-]+|[a-z][a-z0-9]*(?:-[a-z0-9]+)+-\d{3}|CO-\d{3})\b")
SHA_RX = re.compile(r"\b[0-9a-f]{7,40}\b")
# A coordinator receipt posted WITHOUT the MAIN marker (2026-10-16: c6219240110 "ACK — aria-appointment-verification-001
# (session caoscare-1-e7)", c6219463449 "DONE — ... (session caoscare-1-e7)") is recognised only by its exact shape: the
# FIRST line starts with the state keyword (no quote marker), names an item id, and names a session that exists in Claude
# Code's own session registry. Owner prose that merely contains ACK/DONE, or quotes a receipt ("> ACK ..."), is not one.
UNMARKED_RECEIPT_RX = re.compile(r"^(ACK|WORKING|DONE|BLOCKED)\b[^\n]{0,8}?" + ITEM_RX.pattern + r"[^\n]*\(session (?P<session>caoscare-1-[0-9a-z]+)\)")
SESSION_RX = re.compile(r"\bsession[\s:`*]+(caoscare-1-[0-9a-z]+)\b")
CMD_RX = re.compile(r"(?:\bc|issuecomment-)(\d{9,12})\b")   # an owner command cited as c6222902220 or by its URL


def gh_json(args: list, timeout: int = 60):
    r = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"gh api failed: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout or "null")


def comments_since(repo: str, number: int, since_iso: str, max_pages: int = 20) -> list:
    """Every comment updated since `since_iso`, all pages (a burst of >100 comments must not be dropped)."""
    out = []
    for page in range(1, max_pages + 1):
        batch = gh_json([f"repos/{repo}/issues/{number}/comments?since={since_iso}&per_page=100&page={page}"]) or []
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


def post_comment(repo: str, number: int, body: str) -> str:
    out = gh_json([f"repos/{repo}/issues/{number}/comments", "-f", f"body={body}"])
    return out.get("html_url", "")


def classify(c: dict, owner_logins=("caosos",), known_sessions=None) -> dict:
    body = c.get("body") or ""
    head = body[:400]
    kind = "other"
    if WATCH in body:
        kind = "watcher"
    elif MAIN in body:
        kind = "coordinator_receipt"
    elif DA in body:
        kind = "da_delivery"
    elif RECV in body:
        kind = "receiver_status"
    elif (c.get("user") or {}).get("login") in owner_logins:
        kind = "owner_directive"
    first_raw = next((ln.strip() for ln in body.strip().splitlines() if ln.strip() and not ln.strip().startswith("<!--")), "")
    unmarked = UNMARKED_RECEIPT_RX.match(first_raw)
    if kind == "owner_directive" and unmarked and known_sessions is not None and unmarked.group("session") in known_sessions:
        kind = "coordinator_receipt"            # verified provenance: registry-known session named in the receipt line
    head_up = NEGATED_RX.sub(" ", head.upper())          # "not deployed" is not DEPLOYED
    first = next((ln for ln in body.strip().splitlines() if ln.strip() and not ln.strip().startswith("<!--")), "")
    header_up = NEGATED_RX.sub(" ", first.upper())
    # State comes from the receipt's leading keyword ("WORKING <item> ..."), then its header line, and only
    # then from the first 400 chars: body text like "Nursing Done Today" or "acceptance passed" must not
    # turn a WORKING receipt into DONE (2026-10-16: a not-DONE receipt was recorded as the slice's DONE).
    lead = LEAD_RX.match(header_up)
    state = lead.group(1) if lead else "none"
    for text in (header_up, head_up):
        if state != "none":
            break
        for name, rx in STATE_RX:
            if rx.search(text):
                state = name
                break
    # a release boundary is a coordinator receipt whose HEADER names the release/production/deploy AND a completion word
    boundary = kind == "coordinator_receipt" and bool(BOUNDARY_RX.search(header_up)) and bool(BOUNDARY_DONE_RX.search(header_up))
    lines = [ln for ln in body.strip().splitlines() if ln.strip() and not ln.strip().startswith("<!--")]
    sess = SESSION_RX.search("\n".join(lines[:3]))
    return {"kind": kind, "state": state, "boundary": boundary, "items": sorted(set(ITEM_RX.findall(body[:2000]))),
            # an owner command's own task ids come from its heading: the first line that names an item (the body may cite
            # other items as examples, e.g. c6222902220 cites aria-appointment-verification-001)
            "tasks": sorted(set(next((ITEM_RX.findall(ln) for ln in lines[:12] if ITEM_RX.search(ln)), []))), "commands": sorted(set(CMD_RX.findall(body[:3000]))),
            "session": sess.group(1) if sess else None, "unmarked": kind == "coordinator_receipt" and MAIN not in body,
            "shas": SHA_RX.findall(head)[:3], "url": c.get("html_url"), "created_at": c.get("created_at"),
            "id": c.get("id"), "header": re.sub(r"<!--.*?-->", "", first)[:160].strip()}


def chicago(ts_iso=None) -> str:
    from zoneinfo import ZoneInfo
    t = datetime.fromisoformat(ts_iso.replace("Z", "+00:00")) if ts_iso else datetime.now(timezone.utc)
    return t.astimezone(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S %Z")


def receipt_body(title: str, fields: dict, wake: bool = False, mirror: bool = False) -> str:
    """One receipt with the owner's required fields in fixed order. wake=True omits MAIN so Main
    Claude's watch picks it up (deliveries only). mirror=True is the PR transport form whose
    first line begins 'CAOSCARE RECEIPT:' so the ChatGPT supervisor wakes."""
    order = ["timestamp", "task", "coordinator", "state", "branch", "head_sha", "tested_sha", "loaded_sha",
             "host_state", "last_host_evidence", "receipt/evidence", "eta", "next_check_at", "blocker", "next_action"]
    lines = [f"- **{k}:** {fields[k] if fields.get(k) not in (None, '') else 'UNKNOWN'}" for k in order]
    markers = WATCH if wake else WATCH + MAIN
    head = f"CAOSCARE RECEIPT: {title}" if mirror else f"CAOSCARE WATCH RECEIPT — {title}"
    return f"{markers}\n{head}\n\n" + "\n".join(lines) + "\n"
