# Therapy appointment loop — build + browser acceptance (careops-therapy-appointment-001) — 2026-10-11

Dispatch (#129 comment 6107675195): on canonical appointment/task/receipt records, with labelled synthetic data, one
non-recurring therapy appointment from staff creation through resident/staff schedule visibility, one reschedule,
attendance completion or cancellation, linked receipts. No recurrence, billing, external messaging, audio, deploy, or new
parallel truth store.

## Canonical record (finding)
There is no appointment model. A therapy appointment is a **StaffTask in the `therapy` department** whose planned visit window
is the existing pair `requested_for_date` / `requested_for_time_label` (set through `PATCH /tasks/{id}`, receipted as
`task_schedule_updated`, read by the resident Home screen and Aria as `scheduled_date` / `scheduled_time_label`). Creation,
claim, start, complete, skip, reopen and history are the ordinary lifecycle actions. Nothing new was modelled.

## What was built (bounded to the gaps found)
1. **Therapy (and every remaining department) works the shared queue.** `DepartmentWorkspace.jsx` rendered a separate
   generic Ack/Start/Done list for departments other than maintenance/transportation/services, with no notes, history, plan or
   cancel. It now renders the same `DepartmentQueue` nursing, maintenance and housekeeping use (the duplicate list is removed,
   −115 lines). `roleHome.js`: `therapy` and `resident_programs` staff land on `/workspace` (were sent to the nursing board).
2. **Planned window on the queue card** ("Planned: 10:00 AM · 2026-10-14") and a **Plan** dialog (date + time label) that saves
   the same two fields the admin/front-desk detail dialog saves. New `QueueDialogs.jsx` (PlanWindowDialog, ReasonDialog).
3. **Cancel with a reason** in the queue = the canonical skip (`POST /tasks/{id}/skip`, receipted `task_cancelled`, reason
   in history). Submit disabled until a reason is typed.
4. **Resident visibility of front-desk-entered requests.** `RESIDENT_ORIGIN_SOURCES` (the one list the resident view, Aria's
   status and Layer E use) gains `front_desk`: a request entered at the desk on the resident's behalf rides the same bus and is
   the resident's request, so the resident's Home screen and Aria now see it. Before, an appointment entered at the desk was
   invisible to the resident.
5. **Defect fixed:** `aria_request_status._sched()` read the window from the view's field names but was always handed the raw
   task, so a planned window was never spoken in any state. It now reads the task's fields (view names still accepted).

## Setup (silent, isolated)
Scratch stack only: DB `caoscare_therapy_acc` (copy of the public demo data, plus the `therapy` department and one labelled
synthetic therapist `Demo - Tess Ortiz PT`, staff role), backend `:8135` on this tree (OpenAI/HA/Resend/Twilio blank), frontend
`:3018` proxied to it; headless Chrome (fake media devices, muted); accounts via the normal login API; resident
`Demo - Betty Owusu` (room 3W03). The owner's browser and the shared dev DB were not touched. The two console errors seen are
the kiosk page's menu/schedule reads to caoscare.com from a non-production origin (the EliteDesk-only env override), not this
work.

## Result: 21 / 21 cases, 0 failed API calls, 0 page errors (`task_68b27f1c79ca`, cancelled `task_62644000faa9`)
| # | Case | Result |
|---|---|---|
| 1 | Front desk: New request → Betty Owusu → Department **Therapy** → "Request sent" → `visibility_role therapy`, `source front_desk` | PASS |
| 2–3 | Not in the front desk's Administration queue; visible under All requests | PASS |
| 4 | Front desk cannot plan it: `PATCH /tasks/{id}` → 403, nothing written | PASS |
| 5 | Therapist signs in → `/workspace` shows "Therapy requests" (shared queue) with the appointment | PASS |
| 6 | **Plan** 10:00 AM on D+3 → "Plan saved — the resident and Aria will see it" → card "Planned: 10:00 AM · D+3" | PASS |
| 7 | **Reschedule** to 2:00 PM on D+4 → card updated | PASS |
| 8 | Two `task_schedule_updated` receipts; before/after carry the windows | PASS |
| 9 | Resident view (`/tasks/resident-request/mine`) shows the window | PASS |
| 10 | Aria status: "…Planned for 2:00 PM on D+4." | PASS |
| 11 | Resident Home screen (kiosk, no session started): THERAPY · RECEIVED · Planned: 2:00 PM · D+4 | PASS |
| 12 | Attendance: Claim → Start → Complete with note → Recently completed | PASS |
| 13 | History: Created (front desk), Visit window set ×2, Claimed, Started, Note, Completed | PASS |
| 14 | Receipt chain `resident_request_created → task_schedule_updated ×2 → task_assigned → task_in_progress → task_completed`, each parent = previous, one workflow id | PASS |
| 15 | Resident history: "taken care of by Demo - Tess Ortiz PT" | PASS |
| 16 | Second appointment (front desk, API) appears in the therapy queue | PASS |
| 17 | Cancel submit disabled until a reason is typed | PASS |
| 18 | **Cancel** with reason → `skipped`, one `task_cancelled` receipt with the reason, chained to the plan receipt | PASS |
| 19–20 | Not in the open queue; resident status reports nothing open | PASS |
| 21 | 390 px: therapy workspace renders the shared queue, no overflow | PASS |

Screenshots (`docs/reports/assets/2026-10-11-therapy/`): `01_fd_created_all_requests`, `02_therapist_queue`, `03_planned`,
`04_resident_home`, `05_history`, `06_cancel_dialog`, `07_390_workspace`.

## Tests
- Backend gate on this tree: see PROJECT_STATE entry (new `tests/test_therapy_appointment.py`: therapy-only visibility, front-desk
  403 with nothing written, plan + reschedule receipts with before/after, resident view and spoken window, attendance chain,
  cancel with reason, nothing open afterwards).
- Frontend 68 suites / 561: new `departmentQueuePlanCancel.test.js` (planned line, Plan PATCH payload, Cancel reason + skip
  payload); `roleHome.test.js` updated (therapy → workspace; an unknown custom department still → `/staff`). CI build compiled.

## Observations / not done
- Two "Refresh" controls are visible on the workspace (the page header's and the queue's own); cosmetic.
- The therapy workspace has no calendar view; appointments are listed as requests with their planned window (sorted by age, not
  by date). A date-ordered "upcoming" view is a candidate follow-up, not built.
- Transportation link: not needed for this scenario (no ride); not touched.
- Not deployed; the shared dev backend (:8092) is restarted on this code only after the gate.
