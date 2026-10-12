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

## Addendum — close receipts (careops-alerts-close-receipts-001, `fc9e95b`)
Gaps 2 and 4 repaired. `resolve` and `close` now share `_finish()`: one atomic write guarded on
`status in active/acknowledged/escalated` (legacy `escalated` included), a history entry linked to an
`alert_completed` receipt that names actor, role, department, authority, the origin receipt as parent, and
before/after (including outcome and category). A repeat or concurrent close/resolve gets 409 and changes nothing;
before this, close could re-close a resolved alert and overwrite who/when, and the completion receipt existed only
when the alert had an origin receipt and had no actor.
- Tests: `backend/tests/test_alert_close_receipt.py` (active close, acknowledged resolve, legacy escalated, repeat
  close/resolve 409 with nothing rewritten, 6 concurrent closes → one winner/receipt/history entry, unknown 404)
  failed before (no receipt), passes after. `test_alert_receipts_append_only.py` updated to the single close path
  (first receipt byte-identical, completion receipt parented to it). Backend 605 passed / 0 failed / 31 skipped.
- Browser (dev `fc9e95b`, synthetic DEMO alert, no live Aria lease): nurse at 390 px closed it from
  `/staff?alert=…` with an outcome (no overflow, no failed API calls); owner `/alerts?status=resolved` at 1280 lists
  it resolved (cards do not print the outcome; it is on the receipt and in the detail dialog); one `alert_completed`
  receipt with the nurse as actor, linked to the history entry; repeat close and resolve 409 with outcome and
  `resolved_by` unchanged; room-screen public status `resolved` and minimal.
- Still open: acknowledgement/close role policy (owner decision); direct wander/wearable/pendant inserts.

## Addendum — device ingress (careops-alerts-ingress-receipts-001, `004c158`)
Gap 3 repaired. `location.py` (geofence), `wearables.py` and `pendants.py` (retired scaffold) inserted alerts
directly: one alert per signal (9 wearable signals → 9 alerts before the fix), no coalescing, no creation receipt.
They now call `record_resident_activation`:
- a button press (wearable `press`, pendant `press`) is a press (`presses[]`, `press_count`);
- fall / heart-rate / inactivity / geofence is a **device signal** (`semantic_class = device_signal`), recorded in a new
  `signals[]` list, never `press_count`; it can only raise severity, logged in `event_log`;
- the creation receipt now carries actor (resident claim for a press, the device for a signal), identity basis,
  authority `resident_ingress:<source>`, device id and after-state; source identity (`pendant_id`, frequency, zone)
  is kept on a new event; the pendant scaffold's "second press within 60 s → emergency" is kept as a logged upgrade.
- RF supervisory frames are still refused (only `help_press` and `device_signal` pass the guard).
- Tests: `backend/tests/test_alert_ingress_receipts.py` (inactivity + 6 concurrent falls + press + inactivity →
  one event, emergency, press_count 1, 8 signals, one creation receipt; pendant two presses → one event, press 2,
  emergency; geofence breaches → one event with 2 signals, zone kept). Fails on the old code (9 alerts), passes now.
  Old tests (`backend_test` geofence, `iter7` pendant, `iter9` wearable) expected one alert per signal and were updated
  to the one-open-event rule. Backend 606 passed / 0 failed / 31 skipped.
- Browser (dev `004c158`, temporary wearable on demo resident 3W02, no open event or lease before): four wearable
  signals → one emergency event; nurse `/staff` at 390 shows one card (no overflow, no failed API calls); owner
  `/alerts` at 1280 lists it; public status minimal; acknowledge and close still work; temp wearable removed, nothing
  left open.
- Still open: who may acknowledge/close (owner decision).
