# Owner instruction intake (RQ-042) - receiving side

## The split
- **Desktop-Agent** polls GitHub (issue #117 and owner-instruction issues), assigns item ids (`da-<hex>`), keeps its own receipts and posts a DELIVERED comment.
- **CAOSCare** (this repo, `scripts/owner_intake/receiver.py`) only acknowledges: it records that the coordinator received an item and posts the status comment. No polling, no timers, no nudges, no model calls, no new secrets (uses the existing `gh` login).

## Commands
- `receiver.py received <item_id> --issue N [--note T]` - record receipt (idempotent).
- `receiver.py status <item_id> ACK|WORKING|BLOCKED|DONE --issue N [--note T] [--post]` - append the status; with `--post`, post ONE issue comment.
- `receiver.py list [--open]` - items and their latest status; `--open` hides DONE.
- Ledger: `~/.local/state/caoscare-intake/ledger.jsonl` (`CAOS_INTAKE_DIR`), append-only. Repo override: `CAOS_INTAKE_REPO` (default `caosos/CAOSCARE.COM`); `gh` override: `CAOS_INTAKE_GH`.

## Comment format
Exactly:
```
<!-- caos:coordinator -->
ACK <item_id> <note>
```
(`WORKING`, `BLOCKED`, `DONE` the same way; the note is optional.) The marker lets readers tell the coordinator's comments from the owner's, since both use one GitHub login. The same (item_id, status) is never posted twice, and one call posts at most once. A failed post is not recorded, so repeating the command retries it.

## Delivery truth
- A peer message from Desktop-Agent reaches a live Claude session only at its next tool round, so it may wait. The **issue comment is the durable record**.
- Fallback: the coordinator re-reads the issue at each scheduled check (about every 20-25 minutes), so nothing depends on the live message alone.
- "ACK" in the ledger and on the issue is the only proof the coordinator saw an item; Desktop-Agent's DELIVERED comment proves only that it was handed over.

## Tests
`~/CAOSCARE-INTEGRATION/backend/.venv/bin/python3 -m pytest scripts/owner_intake` (stub `gh`, no network).
