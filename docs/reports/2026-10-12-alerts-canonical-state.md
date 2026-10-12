# Alerts: canonical state contract and first repair — 2026-10-12

Task `careops-alerts-canonical-state-001`. Dev stack, synthetic data, production unchanged.

## Inventory (what exists today)
| Record | State fields | Who writes | Receipt today |
|---|---|---|---|
| Alert (resident-assistance event) | `status` active → acknowledged → resolved (legacy rows may say `escalated`) | create: `resident_activation.record_resident_activation` (kiosk button, pendant, AI triage via `ai_escalation`); also direct inserts in `location.py` (wander), `wearables.py`, `pendants.py` (retired scaffold) | create: `resident_assistance_event` / ai receipts; **wander/wearable/pendant inserts: none** |
| | `escalation_level` 0–3 | only `escalation_tick.run_tick` (RQ-018) | `alert_escalated` per level (system actor, rule authority) |
| | acknowledgement | `POST /alerts/{id}/acknowledge` | **none before this change** |
| | resolution | `POST /alerts/{id}/resolve`, `/close`; `operations_currency` legacy close | `alert_completed` (no actor fields); legacy close `alert_legacy_closed` |
| | `aria_state`, `live_line_state` | `alert_lifecycle_events`, `realtime_room_lease`, `resident_session_binding` | event_log only (separate concerns, kept separate per ENGINEERING_CONTRACT decision 8) |
| | dispatch (`dispatch_status`) | `staff_dispatch` | receipted |
| StaffTask (requests) | pending/in_progress/completed/skipped + `needs_review`, `unclaimed_escalated_at` | `task_lifecycle.transition` only | one receipt per step, chained |
| Notification | logged/sent/delivered/failed/simulated | `notification_delivery` | linked to task/alert + receipt (SC-8, RQ-027) |

## Canonical contract (selected — matches ENGINEERING_CONTRACT decisions 5, 6, 8)
1. An alert's staff workflow is `status`: active → acknowledged → resolved. `escalated` is a legacy value only; it is
   treated as open and acknowledgeable, never written.
2. Escalation level is set only by the tick, only while the alert is open, unacknowledged and not stale; it stops at
   acknowledgement or resolution (proven in RQ-018 tests and again here).
3. Every staff transition (acknowledge, resolve/close) is one status-guarded atomic write plus a receipt naming actor,
   authority and before/after, with a history (`event_log`) entry carrying that receipt id. Repeats and concurrent
   attempts have one winner.
4. Requests (StaffTask) keep their own lifecycle; the accepted Nursing unclaimed escalation is a StaffTask transition
   (`task_unclaimed_escalated`, system actor) and is not an alert. It maps to this contract unchanged: system actor,
   one receipt, idempotent claim, stops when claimed or closed.
5. The room screen reads only `GET /alerts/public/{id}/status` (`alert_id`, `status`, `severity`).

## First proven gap and repair (`45bd442`)
Acknowledging an alert stops escalation and marks the linked nursing dispatch delivered, but wrote **no receipt and no
history entry**. Now: one atomic write (filter `status in active/escalated`) sets acknowledged and appends an
`event_log` entry whose `receipt_id` is the `alert_acknowledged` receipt written next (actor, role, department,
authority, before/after). Test `backend/tests/test_alert_acknowledge_receipt.py` failed before (no receipt), passes
after: one receipt, history entry linked, repeat refused (404, nothing written), 6 concurrent acknowledgements → one
winner/one receipt/one history entry, escalation stays 0 after acknowledgement, a legacy `escalated` row acknowledged
with `before_state.status = escalated`.

## Evidence
- Backend gate 604 passed / 0 failed / 31 skipped (`45bd442`); alert/escalation/dispatch focused tests 15/15.
  Frontend unchanged (last 90 suites / 642).
- Browser (headless, dev `45bd442`, synthetic alert in room DEMO via the canonical `POST /alerts`, no live Aria lease):
  nurse at 390 px acknowledged from `/staff` (no overflow, no failed API calls); owner `/alerts` at 1280 shows
  "acknowledged by Demo - Nancy Reyes RN"; receipt `rcpt_43a2883ae8cb` `alert_acknowledged`, authority
  `signed_in:staff`, matches the stored history entry; repeat ack 404; public room-screen status minimal; owner
  closed it afterwards. Screenshots in `assets/2026-10-12-alerts-canonical-state/`.

## Not repaired (next gaps, in order)
1. **Who may acknowledge is not restricted**: any signed-in role (e.g. Kitchen) can acknowledge a help alert, which
   stops escalation. The receipt now records the role (`signed_in:<role>`), so it is visible, but refusing it needs
   an owner decision on which roles may acknowledge.
2. `alert_completed` (resolve/close) has no actor or before/after; `/close` can re-close an already resolved alert,
   overwriting `resolved_at`/`resolved_by`.
3. Wander (`location.py`), wearable and the retired pendant scaffold insert alerts directly: no coalescing with the open
   event and no creation receipt.
4. `resolve` ignores legacy `escalated` rows.
