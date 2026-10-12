# Escalation loop liveness — careops-alerts-loop-liveness-001 (2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED (backend). Alerts section not owner-accepted.

## Contract (extends `2026-10-12-alerts-fallback-contract.md`)
- `/api/health` reports `escalation: {state, interval_seconds, last_tick_at}`. **Only `running` means alerts are being escalated.** `starting` (no tick yet), `failing` (last tick raised), `stale` (no tick for > 3 intervals + 60 s), `stopped` (loop task ended), `disabled` (switched off at startup). `ok` keeps meaning "service and database up", so existing deploy/restart checks (`grep '"ok":true'`, HTTP 200) are unchanged.
- Switching escalation off (`CAOSCARE_ESCALATION_AUTO=0`) writes one `escalation_schedule_disabled` receipt on that change of state — actor `system:escalation`, authority `env:CAOSCARE_ESCALATION_AUTO`, before `{tick: healthy|failing}`, after `{tick: disabled}`, parent = previous schedule receipt, `next_state: not_escalating_until_enabled`. Restarting while still off adds nothing. Switching it back on: the first good tick writes `escalation_tick_recovered` chained to it.
- None of these states touch alerts: they stay listed, acknowledgeable and closable; no escalation level, SMS or call is recorded while not running.
- **Process loss** (backend down): `/api/health` does not answer at all, which is what `restart_dev_backend.sh` / `deploy_caoscare.sh` already check. The existing local watchdog (`scripts/owner_intake/heartbeat_probe.py`, run by the Desktop-Agent bridge) watches coordinator/worker progress, not the product backend; wiring it to `/api/health` belongs to that control plane and was not added here (no new monitor).
- **Stopped/stale is reported, not receipted:** `/api/health` is a read and does not write. A receipt for a loop that dies while the process lives would need a writer outside the loop. Next candidate, if wanted.

## First gap and repair
Failing before (`backend/tests/test_escalation_liveness.py`, against the gate server, which starts with the loop OFF): `/api/health` = `{"ok": true, "db": "up"}`, no escalation state, no receipt. Fixed: `escalation.state = disabled`, exactly one receipt, a second start while off adds none, an ended task reads `stopped`; a nurse still sees and acknowledges a synthetic alert with no escalation/SMS/call receipt.

## Gates
Backend 610 passed / 0 failed / 31 skipped. Frontend untouched (91 / 644). No UI change; browser not required. Test cleanup in `finally`.
