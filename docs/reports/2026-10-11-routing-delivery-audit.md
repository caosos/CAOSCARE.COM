# Routing / delivery audit — careops-routing-delivery-audit-001 — 2026-10-11

Owner review (16:49 CDT): a "What's for supper tonight?" request showed as a Kitchen request, Pending — proof of routing
to a department, not of any worker being told or acting. Acceptance: trace one synthetic resident request through
creation → Kitchen delivery → named worker claim/assignment → acknowledgement → completion with timestamps and linked
receipts; detect any lost/aging request; repair the first proven broken transition.

## Trace (scratch stack, API, before any change)
| Step | Observed |
|---|---|
| 1 Create (room-screen/Aria bus, `aria_voice`) | 200, one task, not a duplicate |
| 2 Routing | `visibility_role kitchen`, pending, unassigned |
| 3 Department notification | one record to the Kitchen staff member, status **`logged`** (no email/SMS provider) |
| 4 Kitchen staff queue | present |
| 5 Operations overview | attention tier 5 "Unassigned - no owner" |
| 6 Resident / Aria status | "still open … no one has picked it up yet" (truthful) |
| 7 Kitchen department board | in Unassigned |
| 8 Assign → acknowledge → start → complete (kitchen user) | all 200 |
| 9 Receipts | 5, chained parent→origin, one workflow id, actor named on each step |
| 10 Resident history | "taken care of by <cook>. Their note (…): …" |

**First proven gap:** step 3. The request was "delivered" only into a database record: no provider is configured, so nobody
was emailed or texted, and *no screen said so*. The card, the board and the overview all showed an ordinary Pending /
Unassigned item, indistinguishable from one the department had actually been told about. Every other transition worked.
No request was lost: it stayed visible in the queue, the board and the overview's attention list (with its age).

## Repair
- `backend/routes/request_delivery.py` (new): one read of the notification records linked to each request
  (`related_object_id`, written by `notify_department` since SC-8) → one truthful state, best evidence first: delivered,
  sent (not yet confirmed), simulated, **not_sent** (recorded only, no provider), failed, none. Nothing stored.
- Carried by `GET /tasks/{id}/detail` (`delivery`), the department board rows (+ `counts.not_notified`) and the overview's
  task attention rows (+ `tasks.not_notified_open`).
- Shown: request detail dialog ("Department notification: …" with the intended recipients), department board card and
  overview attention row (a warning line only when the department was not reached).

## Tests
- Backend gate **545 passed, 0 failed, 31 skipped** (+2 in `test_request_delivery.py`: summary states; detail/board/overview
  say `not_sent` with the intended recipient, flip to delivered when the provider reports it, and `none` when no record
  exists). Existing `test_ops_overview.py` unchanged and passing.
- Frontend **76 suites / 590** (board test: warning shown for an unreached request, nothing extra for a reached one); build compiled.
- Browser (scratch stack, headless): **7/7, 0 failed API calls** — overview row, Kitchen board card and detail dialog each
  say "Department NOT notified: recorded only, no email/SMS provider is set up" (dialog names the intended recipient); the
  kitchen user claims → starts → completes in the real queue; receipts chain to `task_completed`; the resident's history
  names the cook and the note. Screenshots: `docs/reports/assets/2026-10-11-routing-delivery/`.

## What this does not fix
- Real delivery needs the email/SMS provider (owner/provider item, RQ-005). Until then every routed request will say
  "not notified" — truthfully.
- A "what's for supper" question routes to Kitchen only because no menu is published for today; publishing the menu (P1
  Menu item) lets Aria answer it directly.
- Not deployed; production `ff87c22`.
