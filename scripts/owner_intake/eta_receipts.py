#!/usr/bin/env python3
"""ETA-driven receipts and exception alerts (owner operating addendum, 2026-10-11, #129 comment 6115336898).

One module owns the receipt schema and the rules; the coordinator writes receipts with it and the local
watchdog (heartbeat_probe.py, run by the Desktop-Agent bridge) reads the current next_check_at from the same
intake ledger. No new tracker: rows go to <CAOS_INTAKE_DIR>/ledger.jsonl with kind "eta".

Rules:
  * ACK / WORKING carry project, task_id, owner, stage, evidence, eta, next_check_at (America/Chicago, exact),
    acceptance, blocker (or NONE).
  * At next_check_at exactly one of WORKING (revised eta + new next_check_at), DONE (commit, tests, evidence,
    loaded revision, host observation, user-visible result, timestamp, next item), NEED/BLOCKED (blocker,
    action, impact, compatible work, next check).
  * DONE may be published early (immediately, not at the check). WORKING before the check is not required.
  * A missed check is an exception: "APPEARS STALE — HOST STATE UNVERIFIED" unless host evidence proves more.
  * Michael is notified only for: DONE needing owner acceptance, NEED/BLOCKED, missed ACK/ETA/check, failed
    test/delivery/deployment/recovery, owner decision, material cost/authority boundary.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")
INTAKE_DIR = Path(os.environ.get("CAOS_INTAKE_DIR", Path.home() / ".local/state/caoscare-intake"))
STALE = "APPEARS STALE — HOST STATE UNVERIFIED"
GRACE_MIN = float(os.environ.get("CAOS_CHECK_GRACE_MINUTES", "10"))
REQUIRED = {
    "ACK": ("project", "task_id", "owner", "stage", "evidence", "eta", "next_check_at", "acceptance", "blocker"),
    "WORKING": ("project", "task_id", "owner", "stage", "evidence", "eta", "next_check_at", "acceptance", "blocker"),
    "DONE": ("project", "task_id", "owner", "commit", "tests", "evidence", "loaded_revision", "host_observation",
             "user_visible_result", "timestamp", "next_item"),
    "NEED": ("project", "task_id", "owner", "blocker", "action", "impact", "compatible_work", "next_check_at"),
    "BLOCKED": ("project", "task_id", "owner", "blocker", "action", "impact", "compatible_work", "next_check_at"),
}
NOTIFY_FLAGS = ("owner_acceptance", "failed_test", "failed_delivery", "failed_deployment", "failed_recovery",
                "owner_decision", "material_cost", "authority_boundary")


class ReceiptError(ValueError):
    pass


def parse_ts(v) -> datetime:
    """An exact, timezone-aware time; a naive value is refused (no guessing)."""
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError as e:
        raise ReceiptError(f"not a timestamp: {v!r}") from e
    if t.tzinfo is None:
        raise ReceiptError(f"timestamp has no timezone: {v!r}")
    return t


def build(kind: str, **f) -> dict:
    """Validate and return one receipt. Raises ReceiptError naming every missing field."""
    if kind not in REQUIRED:
        raise ReceiptError(f"kind must be one of {', '.join(REQUIRED)}")
    missing = [k for k in REQUIRED[kind] if not str(f.get(k) or "").strip()]
    if missing:
        raise ReceiptError(f"{kind} receipt missing: {', '.join(missing)}")
    r = {"kind": kind, **{k: f[k] for k in f if f[k] is not None}}
    if "next_check_at" in r:
        r["next_check_at"] = parse_ts(r["next_check_at"]).astimezone(TZ).isoformat()
    r.setdefault("recorded_at", datetime.now(TZ).isoformat())
    return r


def render(r: dict) -> str:
    """One #129-ready line block; field order fixed so receipts read the same every time."""
    order = [k for k in ("project", "task_id", "owner", "stage", "evidence", "eta", "next_check_at", "acceptance", "blocker",
                         "commit", "tests", "loaded_revision", "host_observation", "user_visible_result", "cost", "timestamp",
                         "next_item", "action", "impact", "compatible_work") if r.get(k)]
    return f"{r['kind']} {r.get('item_id', '')}".strip() + " — " + " | ".join(f"{k}: {r[k]}" for k in order)


def due(r: dict, now: datetime) -> bool:
    return "next_check_at" in r and now >= parse_ts(r["next_check_at"])


def outcome(r: dict, obs: dict, now: datetime) -> str | None:
    """Which receipt the watchdog must publish now, given the last ACK/WORKING `r` and a host observation:
    DONE as soon as it is done (early allowed), NEED/BLOCKED as soon as blocked, WORKING only once the check
    is due (with a revised ETA and a new next_check_at), otherwise nothing."""
    if obs.get("done"):
        return "DONE"
    if obs.get("blocked"):
        return "BLOCKED" if obs.get("hard") else "NEED"
    if due(r, now):
        return "WORKING"
    return None


def missed(r: dict, last_receipt_at, now: datetime, host_alive: bool | None = None) -> dict | None:
    """A check (or ETA) that passed with no newer receipt is an exception. Never claims the worker stopped
    without host evidence."""
    if "next_check_at" not in r:
        return None
    limit = parse_ts(r["next_check_at"]) + timedelta(minutes=GRACE_MIN)
    newer = last_receipt_at and parse_ts(last_receipt_at) > parse_ts(r["next_check_at"])
    if now <= limit or newer:
        return None
    state = "HOST ALIVE, RECEIPT MISSING" if host_alive else ("HOST NOT RUNNING" if host_alive is False else STALE)
    return {"exception": "missed next_check_at", "task_id": r.get("task_id"), "next_check_at": r["next_check_at"],
            "state": state, "minutes_late": int((now - parse_ts(r["next_check_at"])).total_seconds() // 60)}


def should_notify(kind: str, **flags) -> bool:
    """Notify Michael only for the listed exceptions; never for routine healthy progress."""
    if kind in ("NEED", "BLOCKED", "MISSED"):
        return True
    if kind == "DONE":
        return bool(flags.get("owner_acceptance"))
    return any(flags.get(f) for f in NOTIFY_FLAGS)


def ledger_row(r: dict) -> dict:
    """The intake-ledger row for a receipt: kind "eta" marks it, the receipt kind is kept as `receipt`."""
    return {**r, "kind": "eta", "receipt": r["kind"]}


def record(r: dict, ledger_dir: Path = INTAKE_DIR) -> Path:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    p = ledger_dir / "ledger.jsonl"
    with p.open("a") as fh:
        fh.write(json.dumps(ledger_row(r)) + "\n")
    return p


def current(ledger_dir: Path = INTAKE_DIR) -> dict | None:
    """The newest eta receipt in the ledger (the one whose next_check_at is live)."""
    p = ledger_dir / "ledger.jsonl"
    if not p.exists():
        return None
    last = None
    for line in p.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("kind") == "eta":
            last = row
    return last


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Write one ETA-driven receipt (validated) to the intake ledger and print it.")
    ap.add_argument("kind", choices=list(REQUIRED))
    ap.add_argument("--field", "-f", action="append", default=[], help="key=value (repeat)")
    ap.add_argument("--in-minutes", type=float, help="set next_check_at to now + N minutes (America/Chicago)")
    a = ap.parse_args(argv)
    fields = dict(kv.split("=", 1) for kv in a.field)
    if a.in_minutes is not None:
        fields["next_check_at"] = (datetime.now(TZ) + timedelta(minutes=a.in_minutes)).replace(second=0, microsecond=0).isoformat()
    try:
        r = build(a.kind, **fields)
    except ReceiptError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    record(r)
    print(render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
