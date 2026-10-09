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

## Delivery states, observed (2026-10-08 evening, truthful distinction)
| State | Meaning | Proof |
|---|---|---|
| POSTED | Michael's text is on GitHub | the issue comment itself |
| DELIVERED | Desktop-Agent polled it, assigned `da-<hex>` and handed it to this session as a Claude Code peer message; it also posts a DELIVERED comment | the DELIVERED comment + its receipt |
| ACKNOWLEDGED | the coordinator posted `ACK <item_id>` (marker line first) | the ACK comment + `receiver.py` ledger row |
| ACTED | a status `WORKING/BLOCKED/DONE <item_id>` with the evidence | that comment + commit/receipt it cites |

- A new GitHub comment alone does **not** start a Claude turn: nothing in GitHub reaches the CLI. Only Desktop-Agent's peer message does.
- Observed here: when the session is **idle** at its prompt, a peer message starts a processing turn by itself (this heartbeat item, da-46a126825e, and the earlier backfill items did exactly that). When the session is **mid-turn**, it is queued and read at the next tool round. If the session is not running at all, nothing is delivered; the issue comment remains the durable record.

## Heartbeat (RQ-044): bounded and LLM-free
Desktop-Agent is the single central monitor; CAOSCare adds no poller. To wake the coordinator only when there is something to read:
1. The coordinator keeps `docs/status/COORDINATOR_STATUS.json` current at every state change (`ready_unblocked`, `workers`, `questions`, `waiting_owner`).
2. On its own schedule Desktop-Agent runs `python3 scripts/owner_intake/heartbeat_probe.py` (stdlib only, no network, no model, no posting) and gets `{"verdict": "WAKE"|"IDLE", "reasons": [...]}`.
3. IDLE: it does nothing (cost zero). WAKE: it sends one peer message `DA-HEARTBEAT reasons=...` to the coordinator session; the coordinator reads the reasons, acts or answers, and ACKs through the normal comment.
WAKE reasons: ready unblocked work or an open question in the status file; a listed worker's worktree untouched for 45 min; an intake item received but not ACKed for 30 min. Everything else is IDLE. It cannot interrupt Room 214 (it never touches the services, the leases or any audio) and installs nothing on the host.
Limit: it can only reach a live session. If no Claude session is running, the heartbeat has no one to wake; the verdict is still logged by Desktop-Agent and the next owner/operator start reads the status file.

## End-to-end proof (dummy test, 2026-10-08 21:50-21:52 CDT)
| Step | Time (UTC) | Evidence |
|---|---|---|
| POSTED (labelled DUMMY, no care request) | 02:50:58 | comment 6073255443 |
| DELIVERED (Desktop-Agent peer message + DELIVERED comment) | 02:51:53 (55 s) | DELIVERED comment names the live session; the peer message reached this session at its next tool round |
| ACKNOWLEDGED (`ACK da-a7402413a7`, marker first) | 02:51:58 (5 s after delivery) | comment + `receiver.py` ledger rows (`received`, `status ACK posted`) |
| ACTED | n/a | dummy, no action taken |
Not exercised by this test: the delivery was received mid-turn (queued to the next tool round); an idle-wake was observed earlier the same evening (items da-46a126825e and the backfill items began new turns). The heartbeat probe exists and returns IDLE now, but **Desktop-Agent has not yet wired it** to send `DA-HEARTBEAT`; until it does, "wake for queued READY work" is not verified.

## Idle-wake re-proof (dummy test 2, 2026-10-08 21:57-21:58 CDT)
The coordinator posted a labelled DUMMY, ended its turn (idle), and did nothing else:
| Step | Time (UTC) | Gap |
|---|---|---|
| POSTED (comment 6073325841) | 02:57:37 | n/a |
| DELIVERED (peer message to `caoscare-integration-b2`, DELIVERED comment 02:58:02) | 02:58:01 | +24 s |
| New Claude turn started by the message, ACK `da-0cf0297adf` posted | 02:58:06 | +5 s after delivery |
Verdict: **event wake of an idle CAOSCare coordinator is VERIFIED** (two independent items: da-46a126825e +16 s and da-0cf0297adf +5 s from delivery to ACK). **Periodic (heartbeat) wake remains UNVERIFIED** until Desktop-Agent schedules `heartbeat_probe.py`. No care request, no action, no service touched.
