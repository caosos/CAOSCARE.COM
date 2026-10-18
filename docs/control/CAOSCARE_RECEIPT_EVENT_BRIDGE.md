# CAOSCare receipt event bridge — TRANSPORT ONLY / DO NOT MERGE

This documentation-only marker keeps one persistent draft pull request open so
the existing CAOSCare GitHub event supervisor can receive transport events.

It is not a product change, coordinator, worker, queue, watchdog, monitor,
checklist, automation, or source of truth. Do not merge this pull request.

Canonical truth remains:

- Issue #129
- `docs/CAOSCARE_LIVING_PRODUCT_BUILD_CHECKLIST.md`
- `docs/PROJECT_STATE.md`
- receipts produced by the existing EliteDesk coordinator/local watchdog

## Receipt comment contract

The existing local watchdog mirrors each meaningful CAOSCare event into one
deduplicated top-level PR comment beginning `CAOSCARE RECEIPT:`:

- ACK
- WORKING
- DONE
- NEED / BLOCKED
- missed ACK, ETA, or `next_check_at`
- recovery
- next-task dispatch

Each comment includes task ID, responsible coordinator/worker, provenance,
evidence, evidence-based ETA, exact `next_check_at` in America/Chicago,
blocker or NONE, tested state, loaded state, and current host observation or
UNKNOWN.

GitHub activity is never proof of host liveness.

## Acceptance

Configuration is not acceptance. A labeled test receipt must cause the
existing GitHub event supervisor to post an unsolicited visible update in the
owning CAOSCare Work conversation within five minutes.

Governing rule: No action without a receipt. No receipt without provenance.
