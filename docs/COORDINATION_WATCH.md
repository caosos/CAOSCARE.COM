# CAOSCare coordination watch — runbook (owner-authorized 2026-10-16)

**Status:** code on `feature/coordination-watch`; NOT installed, NOT running (see "What is missing"). One
local `systemd --user` service, no model calls, `gh` only ($0 API when idle).

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

## Install (owner-run; refused from the Claude session)
```bash
cp ~/CAOSCARE-COORDINATION/scripts/owner_intake/systemd/caoscare-coordination-watch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now caoscare-coordination-watch
loginctl enable-linger caoscare-1        # already "yes" on this host
systemctl --user status caoscare-coordination-watch --no-pager
```

## What is missing (classifier-refused writes, 2026-10-16)
`scripts/owner_intake/coord_host.py` (host evidence from the session registry) and
`docs/status/COORDINATION_QUEUE.json` (config + queue mirror). Their exact specification is in the draft PR
on `feature/coordination-watch`; without them the service does not start.
