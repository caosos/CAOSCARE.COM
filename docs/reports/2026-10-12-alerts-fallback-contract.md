# Alerts fallback contract — careops-alerts-fallback-contract-001 (2026-10-12)

Status: contract written; part (a) first gap IMPLEMENTED / TESTED / DEV_ACCEPTED (backend). Alerts section not owner-accepted.

## Contract (existing paths only)
**Base rule:** escalation and outside notification are *additions* to the on-site alert, never a condition for it. An alert is created, listed (`GET /alerts/feed`, owner board, nurse view), acknowledged and closed on its own path (`resident_activation`, `alerts.py`). Neither the tick nor SMS failing may hide it, block staff action, or change its `active → acknowledged → resolved` state.

**(a) Escalation tick failing or stopped** (`escalation_tick.tick_once`, run by the lifespan loop every `CAOSCARE_ESCALATION_INTERVAL` s):
1. A failing tick is logged **and** receipted once: `escalation_tick_failed` on `escalation_schedule/default` — actor `system:escalation`, authority `escalation_schedule`, before `{tick: healthy}`, after `{tick: failing, error}`, `result_label: failed`, `next_state: retry_next_interval`. Repeated failures add nothing.
2. The loop keeps retrying each interval; the first good tick writes `escalation_tick_recovered` (parent = the failure receipt) and the tick catches up from `created_at`, so missed levels are applied on recovery.
3. If the receipt store itself is down, only the log line is possible; that is stated, not hidden.
4. **Not yet covered (next gap):** a loop that is not running at all (disabled by `CAOSCARE_ESCALATION_AUTO=0`, or its task gone) leaves no record and nobody is told. Needs a reader of the last tick time on an existing surface.

**(b) SMS / external notification unconfigured or failing** (`notification_delivery.notify_alert_phone`, already compliant — inventory, no change):
- Every attempt is one `db.notifications` record plus a NEW `alert_sms_attempt` / `alert_call_attempt` receipt: `logged` + "Twilio not configured - recorded only, not sent" when unconfigured; `failed` + provider error (receipt `status: failed`, `result_label: failed`) when rejected or raised; `sent` = provider accepted, `result_label: unverified` (never claimed as delivered). Simulated alerts are `simulated`, never sent.
- No phone number in the rule → no attempt and no claim.
- The alert's own state is not touched by any of this.

## First gap and repair (`backend/tests/test_escalation_fallback.py`)
Failing before (driving the real `run_escalation_loop`): three failing ticks → 0 receipts, only log warnings. Fixed: one failure receipt, one chained recovery receipt; meanwhile the synthetic alert stayed in the feed and was acknowledged; `db.notifications` count unchanged (no delivery claimed).

## Gates
Backend 609 passed / 0 failed / 31 skipped. Frontend untouched (91 / 644). No UI code changed: the new receipts appear in the existing Admin receipts / activity lists (generic `GET /receipts`). Browser not required. Cleanup in the test's finally.
