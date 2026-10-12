#!/usr/bin/env python3
"""CAOSCare check-in ledger (owner directive 2026-10-12, #129 comment 6118341041).

One append-only canonical log, docs/status/CHECKIN_LOG.md, one entry per verified check-in, tied to its
receipt (an Issue #129 comment URL). Never rewritten: an entry is only appended; a correction is a new
entry that names the receipt it supersedes. Deduplicated by receipt URL.

Each entry carries the owner's 11 fields:
  when (full America/Chicago date+time) · phase · completed · evidence · current task · remaining steps ·
  upcoming milestones · eta · next_check_at · blocker · michael_action

Usage (fields are key=value; lists use ";" separators):
  checkin_log.py add --receipt URL -f phase=... -f completed=... -f evidence=... -f current="task · owner · stage"
                     -f remaining="a;b" -f upcoming="x;y" -f eta=... -f next_check_at=... -f blocker=NONE
                     -f michael_action=NOTHING [--supersedes URL]
Prints the short Work-conversation update (one line + link to the log).
"""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")
LOG = Path(os.environ.get("CAOS_CHECKIN_LOG", Path(__file__).resolve().parents[2] / "docs/status/CHECKIN_LOG.md"))
LOG_URL = "https://github.com/caosos/CAOSCARE.COM/blob/integration/2026-09-27/docs/status/CHECKIN_LOG.md"
REQUIRED = ("phase", "completed", "evidence", "current", "remaining", "upcoming", "eta", "next_check_at", "blocker", "michael_action")
LABELS = {"phase": "Phase / position", "completed": "Completed since the prior check", "evidence": "Evidence",
          "current": "Current bounded task (owner · stage)", "remaining": "Remaining steps for this milestone",
          "upcoming": "Upcoming milestones", "eta": "ETA", "next_check_at": "next_check_at",
          "blocker": "Blocker", "michael_action": "Michael action required"}
HEADER = "# CAOSCare check-in log\n\nAppend-only. One entry per verified check-in, tied to its receipt. A correction is a new entry naming the receipt it supersedes; earlier entries are never edited.\n"


def receipts_in(text: str) -> set:
    return set(re.findall(r"^- \*\*Receipt:\*\* (\S+)$", text, flags=re.M))


def render(receipt: str, fields: dict, when: str, supersedes: str = None) -> str:
    missing = [k for k in REQUIRED if not str(fields.get(k, "")).strip()]
    if missing:
        raise ValueError("missing: " + ", ".join(missing))
    lines = [f"\n## {when}", f"- **Receipt:** {receipt}"]
    if supersedes:
        lines.append(f"- **Supersedes:** {supersedes}")
    for k in REQUIRED:
        v = str(fields[k])
        if k in ("remaining", "upcoming"):
            items = [x.strip() for x in v.split(";") if x.strip()]
            lines.append(f"- **{LABELS[k]}:**")
            lines += [f"  {i}. {x}" for i, x in enumerate(items, 1)]
        else:
            lines.append(f"- **{LABELS[k]}:** {v}")
    return "\n".join(lines) + "\n"


def add(receipt: str, fields: dict, supersedes: str = None, now: datetime = None, log: Path = LOG) -> tuple:
    if not re.match(r"^https://github\.com/caosos/CAOSCARE\.COM/issues/\d+#issuecomment-\d+$", receipt):
        raise ValueError("receipt must be an Issue comment URL")
    text = log.read_text() if log.exists() else HEADER
    if receipt in receipts_in(text):
        return False, text                       # deduplicated: already logged
    when = (now or datetime.now(TZ)).astimezone(TZ).strftime("%A, %B %-d, %Y — %-I:%M %p America/Chicago")
    entry = render(receipt, fields, when, supersedes)
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists():
        with log.open("a") as fh:
            fh.write(entry)
    else:
        log.write_text(HEADER + entry)
    return True, entry


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--receipt", required=True)
    a.add_argument("--supersedes")
    a.add_argument("-f", action="append", default=[])
    args = ap.parse_args(argv)
    fields = dict(kv.split("=", 1) for kv in args.f)
    try:
        added, _ = add(args.receipt, fields, args.supersedes)
    except ValueError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(("Logged" if added else "Already logged") + f": {fields.get('current', '')} · next check {fields.get('next_check_at', 'MISSING')} · {LOG_URL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
