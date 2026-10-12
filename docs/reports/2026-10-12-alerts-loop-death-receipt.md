# Escalation loop death receipt — careops-alerts-loop-death-receipt-001 (2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED (backend). Alerts section not owner-accepted.

**Path reviewed:** `server.py` lifespan → `escalation_schedule.start_schedule()` creates the loop task; shutdown called `esc_task.cancel()`. Nothing observed the task ending any other way; `/api/health` could show `stopped` with no receipt.

**Failing before** (`backend/tests/test_escalation_loop_death.py`): a loop that raised (`MemoryError`, synthetic) left 0 receipts.

**Repair (`e2e2b1b`):** the task's done-callback writes one `escalation_schedule_stopped` receipt — actor `system:escalation`, authority `escalation_schedule`, before `{tick: healthy}`, after `{tick: stopped, error}`, `status: failed`, `result_label: failed`, `next_state: not_escalating_until_restart`, parent = previous schedule receipt — unless `stop_schedule()` (the lifespan's shutdown) marked the stop intentional. Same state again (a second death, or a cancel that was not a shutdown) adds nothing. The next good tick writes `escalation_tick_recovered` chained to it. No notification or escalation record is created.

**Module split:** schedule + health moved to `backend/routes/escalation_schedule.py` (178 lines); `escalation_tick.py` (141) keeps `run_tick`, rules and SMS escalation. Tests repointed; behaviour unchanged.

**Gates:** backend 611 passed / 0 failed / 31 skipped; frontend untouched (91 / 644); no UI change, no browser. Test cleanup in `finally`.

**Dev:** reloaded; a normal restart (intentional shutdown of the old process) wrote no stopped receipt; health `running`.
