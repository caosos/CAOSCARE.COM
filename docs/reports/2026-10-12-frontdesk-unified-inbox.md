# Front desk unified inbox — inventory and first slice (careops-frontdesk-unified-inbox-inventory-001, 2026-10-12)

Status: first slice IMPLEMENTED / TESTED / DEV_ACCEPTED. The unified inbox as a whole is not complete (see gaps).

## Source → state → action → receipt (existing records only)
| Kind | Canonical source | States | List (auth / scope) | Actions → receipt | Front desk today |
|---|---|---|---|---|---|
| Requests | `db.staff_tasks` (`StaffTask`); desk entry `POST /tasks/resident-request` source `front_desk` → Administration | pending, in_progress, completed, skipped (+ `needs_review`, `unclaimed_escalated_at`) | `GET /tasks` (desk sees all; acts only on administration/all_staff, `task_lifecycle.authority_for`) | assign/ack/start/note/schedule/complete/cancel/reopen → `task_*` receipts chained to `resident_request_created`; refusals `task_*_refused` | "Front desk requests" (Administration queue), "All requests" |
| Callbacks | no separate entity: an Administration `StaffTask` ("call me back …") | as requests | as requests | as requests | as requests |
| Messages | inbound email `db.inbound_emails` (menu/activities lanes only); pager `db.pager_events`; no staff/family message store | received/routed/quarantined/… | `GET /email/inbound/messages` **require_admin**; `/paging/feed` signed-in | system-only (`inbound_email.*`) | none |
| Approvals / review | `StaffTask.needs_review`, unclaimed flag; content drafts; family call permission | flags / draft→approved | `/ops/routing-exceptions` (signed-in, scoped); content/family **admin or content dept** | `/tasks/{id}/review` & `/inspect` ADMIN only; escalate `task_escalated` (acts_for) | (now) Needs attention — can see, open, re-send; cannot resolve review |
| Failed deliveries | `db.notifications` (logged/failed/bounced/…); per-task rollup `request_delivery.summarize` | queued…failed/logged/simulated | `GET /notifications` **require_admin** (desk 403); per-task rollup via `/tasks/{id}/detail` and `/ops/routing-exceptions` | re-send `department_renotified` (acts_for) | (now) per request in Needs attention; alert/family deliveries: none |

## Slice chosen and repaired
The existing read model `/ops/routing-exceptions` (not delivered, failed handoff, unassigned, unclaimed, overdue, optional review) already combines requests + callbacks + delivery state + receipts, and the backend already scopes it to what the front desk acts for — but only Admin had a screen. **Gap:** no front desk surface. **Repair (`2604c16`):** `/front-desk` gets a "Needs attention" tab rendering the same `RoutingExceptionsBoard`. No new store, endpoint or lifecycle.

Failing before: `frontend/src/pages/FrontDeskAttention.test.jsx` (no tab). Contract test (passes on existing backend): `backend/tests/test_front_desk_attention.py` — desk lists its undelivered callback, not a nursing request; re-send receipted `acts_for:administration`; nursing re-send refused; anonymous 401; admin sees both; nothing claimed sent.

## Gates and browser
Backend 614 passed / 0 failed / 31 skipped; frontend 93 suites / 646; build compiled.
Dev headless Chrome 11/11, 0 failed API calls (demo front desk Dana Frost; synthetic requests for demo resident 3W03): desk 1280 sees the callback ("Not delivered · Unassigned · no owner"), not the nursing request; rows = API rows, all Administration; Re-send → `department_renotified` receipt by the desk, nothing sent; Open shows the record; 390 px no overflow; refusals (desk re-send of nursing 403, anonymous 401, desk notification log 403 unchanged); owner API sees both. Cleanup: 2 requests, 3 receipts, 5 logged notifications removed.

## Remaining inbox gaps (not done here)
1. Failed deliveries not tied to a request (alert SMS/calls, family emails) — `GET /notifications` is admin-only; no desk view.
2. Messages — no general message store; inbound email covers menu/activities only and is admin-only.
3. Approvals — desk can see review flags but `/review` and `/inspect` are admin-only (who resolves is an owner/role decision).
4. Callbacks have no callback-time/phone fields (free text).
