# CAOSCare coordination watch — runbook (owner-authorized 2026-10-16)

**Status (2026-10-15 22:30 CDT):** INSTALLED and RUNNING as `caoscare-coordination-watch.service` (user unit,
enabled, linger `yes`), one process, no model calls, `gh` only ($0 API). Proven live: `coord-test-001` (TEST ONLY — NO
PRODUCT ACTION) delivered to #166 and consumed by Main Claude's own intake; after the release boundary the real next item
`careops-153-drilldown-truth-002` was delivered and ACKed by Main Claude (#166 comment 6207381341), and the watcher
detected the ACK. Boundary detection is header-based and negation-aware ("not deployed" is not DEPLOYED) and only
counts receipts on #166/#168; a real item is dispatched only when every earlier delivery is ACKed.

| Question | Answer |
|---|---|
| What owns local watching | `caoscare-coordination-watch.service` (user unit) running `scripts/owner_intake/coordination_watch.py --loop` from `~/CAOSCARE-COORDINATION` every 60 s |
| Where its state lives | `~/.local/state/caoscare-coordination/state.json` (cursor, published keys, dispatched items, last coordinator state) and `events.jsonl` (append-only) |
| How Main Claude receives work | every new owner command on a watched issue is appended to `~/.local/state/caoscare-coordination/inbox.jsonl`. The pinned coordinator session keeps ONE listener armed as its own background command — `python3 scripts/owner_intake/intake_inbox.py listen --session <pinned name>` — which exits on its entry; that exit re-invokes the idle session. The session re-arms it after every wake. The watcher starts nothing (no session, no relay, no model) and verifies the listener runs under the pinned session's own pid (2026-10-16: the in-session GitHub watch this row used to describe had silently disappeared, so nothing was ever picked up). |
| Pickup / idempotency | on any delivery the coordinator first runs `receiver.py pickup c<id> --task <task> --session <name>`: `NEW` = act; `DUPLICATE` (replay) or `COMPLETED` (task already DONE) = do nothing. The ledger row is the observed pickup time; the watcher publishes `PICKUP OBSERVED` from it. |
| What answers an owner command | only a coordinator receipt (MAIN marker, or an unmarked first line `ACK|WORKING|DONE|BLOCKED — <item> (session <registry-known name>)`) posted after the command that cites its `c<id>`/URL or its heading task id. DELIVERED, watcher, Desktop-Agent and other-task receipts never clear it; DONE of one task never closes another. |
| Missed ACK (300 s) | ONE redelivery through the inbox (reported honestly: armed or `NOT armed` with the exact `listen` command), then ONE `NEED_OWNER` if still unanswered 300 s later. Never a second session. |
| Where receipts are published | `CAOSCARE WATCH RECEIPT` comments: deliveries/exceptions on #166 (wake); every other transition mirrored as `CAOSCARE RECEIPT:` on the transport PR #131 (the ChatGPT supervisor's wake line). Routine receipts carry both markers so they never wake Main Claude. |
| Dedup | one receipt per `task + state + source comment id`; the key set is persisted; a repeated event is skipped. Comments are read with every page and a 5-minute overlap window; comment ids (persisted `seen_ids`) decide what is new |
| Stale / blocked detection | host verdict from the Claude session registry + `/proc` (`LIVE_BUSY`, `LIVE_IDLE`, `STALE` after 45 min, `STOPPED` only with pid evidence, `UNVERIFIED` → "APPEARS STALE — HOST STATE UNVERIFIED"); missed ACK after 30 min; `BLOCKED/NEED/FAILED` headers; GitHub silence is never "stopped" |
| Task boundary | a real queue item is dispatched only after the previous real item has a Main Claude **DONE** receipt naming its id (ACK/WORKING is not a boundary), the coordinator is LIVE_IDLE, and every earlier delivery is ACKed; `done-<item>` receipt marks the boundary |
| DONE → next item | `docs/status/COORDINATION_QUEUE.json` mirrors #166's order; dispatch only when the gate is enabled, the required boundary receipt was seen, the coordinator is live and not busy, and every earlier real delivery was ACKed; the test item (`TEST ONLY — NO PRODUCT ACTION`) is ungated |
| Inspect status | `python3 scripts/owner_intake/coordination_watch.py --status`; `systemctl --user status caoscare-coordination-watch`; `journalctl --user -u caoscare-coordination-watch -n 50` |
| Restart / recover | `systemctl --user restart caoscare-coordination-watch`; `Restart=on-failure`; state survives restarts; a STOPPED coordinator produces a NEED_OWNER receipt — recovery is `claude --resume <session id>` by the owner, never automatic |
| Do NOT duplicate | no second watcher, no second queue (#166 is authoritative), no new Claude session, no Desktop-Agent re-pointing from this lane; the tmux `caoscare-integration-b2` coordinator is stood down |
| ChatGPT in the loop | reads #166 and PR #131 `CAOSCARE RECEIPT:` comments; does not run on this host |

## Install / reinstall
```bash
cp ~/CAOSCARE-COORDINATION/scripts/owner_intake/systemd/caoscare-coordination-watch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now caoscare-coordination-watch
loginctl enable-linger caoscare-1        # already "yes" on this host
systemctl --user status caoscare-coordination-watch --no-pager
```

## Dry run
`CAOS_COORD_DRY_RUN=1 python3 scripts/owner_intake/coordination_watch.py --once` posts nothing and persists nothing
(no state, no events, no dispatched marks), so it can never consume a pending delivery.

## Files
`scripts/owner_intake/coordination_watch.py` (loop), `coord_github.py` (gh read/classify/receipts), `coord_queue.py`
(queue mirror + dispatch gate), `coord_host.py` (session registry + /proc host evidence), `tests/test_coordination_watch.py`,
`systemd/caoscare-coordination-watch.service`, `docs/status/COORDINATION_QUEUE.json` (queue mirror, edited by commit only).
