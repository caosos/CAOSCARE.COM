# Alert escalation policy editor — careops-alerts-policy-editor-001 (2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED. Alerts as a section is not owner-accepted.

## Inventory (one store, one editor, one runtime reader)
| Piece | Where |
|---|---|
| Store | `db.escalation_rules`, one doc per `facility_id` (`models.EscalationRule`) |
| Editor | Admin → Reports & audit → Escalation (`frontend/src/pages/EscalationTab.jsx`) |
| API | `GET/PUT /api/escalation/rule`, `POST /api/escalation/tick` (`routes/escalation.py`, owner/admin only) |
| Runtime reader | `routes/escalation_tick.run_tick` (only writer of `escalation_level`), run by the existing lifespan loop every 30 s |
| Defaults / fallback | no stored rule → `EscalationRule()` 90 s / 150 s / nursing unclaimed 600 s |

## First proven gap and repair (`7ade644`)
Failing before (`backend/tests/test_alert_policy_editor.py`): `PUT /escalation/rule` stored level 3 ≤ level 2 with 200 and wrote no receipt.
- `EscalationRule`: each threshold 1 s – 1 day; level 3 must be later than level 2 (422 otherwise).
- An edit is stored only if the rule did not change meanwhile (409), writes an `escalation_rule_changed` receipt — actor, `policy_editor:<role>`, before (stored or defaults) / after, parent = previous edit's receipt — and the stored rule carries `receipt_id` / `updated_by`.
- The editor shows the refusal reason and no longer swaps a blank field for 90/150; it shows when the policy last changed.

## Transition matrix (tested)
| Actor | read | edit | run tick |
|---|---|---|---|
| owner / admin | 200 | 200 (valid) / 422 (invalid) | 200 |
| front desk, nursing staff | 403 | 403 | 403 |
| anonymous | 401 | 401 | 401 |

Runtime: with a 20/40 s policy a 30 s alert reaches level 2 and its `alert_escalated` receipt records thresholds 20/40; a same-age alert at a facility with no rule stays 0 (defaults). Disabling the policy stops further escalation. A second edit chains to the first; the first receipt is unchanged.

## Gates
Backend 607 passed / 0 failed / 31 skipped. Frontend 91 suites / 644 tests (new `EscalationTab.test.jsx`, fails on the old editor). Build OK.

## Development browser acceptance (backend 7ade644, PID 1532821)
11/12 checks; the one "failure" is the browser console logging the deliberate 422. Owner desktop: defaults → invalid edit refused with reason → 20/40 saved with receipt. The existing background tick escalated a synthetic alert under the edited policy. Nurse/front desk refused. 390 px: no overflow; nurse lands on /staff with no editor. Cleanup: rule doc, synthetic alert, and 2 synthetic receipts removed; dev again has no stored rule (defaults). No other open alert was younger than 24 h during the window.

Screenshots: `2026-10-12-alerts-policy-editor/01..05_*.png`; script `acceptance_script.py`.

Not changed: acknowledge/close role policy (owner decision); escalation loop/timer; resident/Aria/public output (escalation level is not in the resident view).
Residue noted, not fixed: `escalate_unclaimed` uses the first stored rule regardless of facility.
