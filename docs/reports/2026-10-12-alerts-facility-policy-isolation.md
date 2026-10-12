# Unclaimed-request escalation: per-facility policy — careops-alerts-facility-policy-isolation-001 (2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED (backend only, no user-visible change).

**Defect (failing before, `backend/tests/test_unclaimed_facility_policy.py`):** `run_tick` passed `next(iter(rules_by_fac.values()), default)` to `escalate_unclaimed`, so the first stored rule's `nursing_unclaimed_seconds` / `enabled` applied to every Nursing request. Reproduced: facility A's 120 s rule flagged facility B's request (B's own rule: 1200 s).

**Repair:** `escalation_tick.rule_for(rules_by_fac, facility_id)` — the facility's own rule, else `EscalationRule` defaults — is used by both the alert loop and the unclaimed step. The unclaimed query uses the shortest threshold in play, then holds each request to its own rule (enabled + threshold). Same store, same tick; nothing added.

**Proof (test):** facilities A (120 s), B (1200 s), disabled facility (60 s, off), and a request with no facility.
At 300 s only A is flagged; at 630 s the no-facility request is flagged (600 s default); at 1300 s B is flagged; the disabled facility is never flagged. Receipt authorities: `escalation_rule:<A>|<B>|default:nursing_unclaimed`, one each.

**Data fact:** today `StaffTask`, `Resident` and `Alert` carry no `facility_id` (dev: 1 facility, 0 tasks/residents/alerts with one), so live requests use the community rule (`facility_id: null`, edited at Admin → Escalation) or the defaults. The test sets `facility_id` on requests directly to model facility-scoped data.

**Gates:** backend 608 passed / 0 failed / 31 skipped (frontend untouched: 91 / 644 unchanged). Browser: not required (no UI change). Cleanup: test-scoped rules, requests, receipts removed by the test.
