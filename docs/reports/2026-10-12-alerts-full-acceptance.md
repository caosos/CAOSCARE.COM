# Alerts — full acceptance run (careops-alerts-full-acceptance-001, 2026-10-12)

**Verdict:** no code change. Every implemented Alerts behaviour passed on development at integration head `8125f1a` (product `e2e2b1b`). **Not READY_FOR_OWNER_REVIEW**: one owner decision (below) and one usability gap (finding 1) remain.

## Gates
Backend 611 passed / 0 failed / 31 skipped; frontend 91 suites / 644 tests; production build compiled.

## Browser run (development, headless Chrome) — 17/17, 0 failed API calls
Demo resident Betty Owusu (room 3W03, kiosk of 3W03), synthetic, cleaned afterwards.

| # | Check | Evidence (final run) |
|---|---|---|
| 1 | 4 concurrent room-screen presses → 1 open event, press_count 4, 1 creation receipt | `alert_064dcb0db986`; `rcpt_1945a7e11631` `resident_assistance_event`, real-human, `resident_ingress:kiosk_button` |
| 2 | Public room-screen status minimal | `{alert_id, status, severity}` only; anonymous full alert / feed → 401 |
| 3 | Owner 1280: invalid policy refused (422); 20/40 s saved with receipt | `rcpt_2da74b63a413` `policy_editor:owner` |
| 4 | Existing background tick escalated under the edited policy | level 3, `rcpt_f26ff1cbbebf` thresholds 20/40; `/api/health` escalation `running` |
| 5 | No external delivery claimed | no SMS/call receipt (no phone configured) |
| 6 | Nurse 390 px acknowledges from `/staff`; receipt + linked history | `rcpt_2371bf59c33e` `signed_in:staff`; event_log entry carries it; escalation stopped (stayed 3 for 35 s) |
| 7 | Refusals | anon ack/close/policy 401; nurse + front desk policy, nurse tick 403; repeat ack 404 |
| 8 | Owner 1280 closes from `/alerts` with outcome | resolved; `rcpt_39fd5f19cbf7` `alert_completed`, owner actor, before acknowledged, parent = origin `rcpt_1945a7e11631` (contract: completion parents the origin) |
| 9 | Repeat close 409, nothing changed; public status `resolved`, still minimal | |
| 10 | No page errors; no horizontal overflow at 390 px (nurse `/staff`, owner `/alerts`) | scrollWidth 390 |

Cleanup: alert, 5 receipts, policy doc and its receipt removed; 0 notifications / dispatches created; resident has no open alert; dev has no stored rule.

## Escalation failure / stop / recovery chain (in-process, scratch DB `caoscare_acc_fa_chain`, dropped)
Dev's own loop was running and was not broken on purpose.
`rcpt_8047363485dc` escalation_tick_failed (healthy→failing) → `rcpt_d9bffd481dfe` escalation_tick_recovered (parent 8047…) → `rcpt_dee70deebe24` escalation_schedule_stopped (parent d9bf…) → `rcpt_d8951bf18e9f` escalation_tick_recovered (parent dee7…). Repeated failures: 1 receipt. Intentional shutdown: none. Actor `system:escalation`, authority `escalation_schedule`. 0 notifications.

## Findings (not fixed here)
1. **Nurse `/staff` "Live alerts" lists 200 weeks-old legacy alerts** (322 open alerts on dev, all older than 24 h — RF test debris). At 390 px the page is ~87,000 px tall with 200 Acknowledge buttons. A new alert still appears first (feed is newest-first) and was acknowledged, but the list is not usable on a phone. The owner `/alerts` board already splits "Current" vs "Older, needs review" (72 h, `alert_is_stale`); `/alerts/feed` does not. **Recommended next item.**
2. The `alert_acknowledged` receipt has no `parent_receipt_id` (the completion receipt links the origin; acknowledgement does not).

## Owner decision packet — who may acknowledge / close a help alert
Today: **any signed-in role** (owner, admin, front desk, any department staff incl. kitchen/maintenance) can acknowledge and close; the receipt records `signed_in:<role>` (owner/admin: `admin_override:<role>`). Anonymous is refused.

| Option | Acknowledge ("I'm on it") | Close (resolve with outcome) | Trade-off |
|---|---|---|---|
| A — keep | any signed-in | any signed-in | fastest response; a non-care worker can close a call for help |
| **B — recommended** | any signed-in | Nursing + owner/admin | anyone nearby can respond; only care staff/leads declare it handled |
| C | Nursing + front desk + owner/admin | Nursing + owner/admin | fewer responders; front desk can still triage |
| D | Nursing + owner/admin | Nursing + owner/admin | strictest; slower if no nurse is near |

Whichever is chosen is enforced in the service (same `_finish` / acknowledge path), refused roles get 403 with nothing written, and the acceptance run is repeated.

Cost: UNKNOWN (none incurred).
