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
| How Main Claude receives work | the intake it already consumes: a comment on issue #166 by the owner login **without** the `<!-- claude-caoscare-session -->` marker; Main Claude's own 60 s GitHub watch exits on it and re-invokes the session with the text. The watcher never starts a session and never sends shell text. |
| Where receipts are published | `CAOSCARE WATCH RECEIPT` comments: deliveries/exceptions on #166 (wake); every other transition mirrored as `CAOSCARE RECEIPT:` on the transport PR #131 (the ChatGPT supervisor's wake line). Routine receipts carry both markers so they never wake Main Claude. |
| Dedup | one receipt per `task + state + source comment id`; the key set is persisted; a repeated event is skipped |
| Stale / blocked detection | host verdict from the Claude session registry + `/proc` (`LIVE_BUSY`, `LIVE_IDLE`, `STALE` after 45 min, `STOPPED` only with pid evidence, `UNVERIFIED` → "APPEARS STALE — HOST STATE UNVERIFIED"); missed ACK after 30 min; `BLOCKED/NEED/FAILED` headers; GitHub silence is never "stopped" |
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
