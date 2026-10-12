# Housekeeping exception lifecycle (careops-housekeeping-exception-lifecycle-001), 2026-10-12

Inspected first: Housekeeping staff (`/workspace`, CommunityServicesWorkspace) and Admin → Housekeeping use the shared
`DepartmentQueue`, so the escalate/review controls and the remount fix already apply. No backend change was needed.
One gap found and fixed: the dialogs' example text was nurse-specific (`675c93e`).

Live on dev (backend `e2a8770`, frontend `675c93e`), demo room, synthetic resident:
1. Typed Aria call rt_c3giegxa_1791792405474: "I spilled juice all over my bathroom floor…" → `request_staff_help`
   housekeeping/high → task_256b9f7a6c7f with the resident's exact words; Aria: "It's on the housekeeping list now…
   I can't say someone is on the way."
2. Demo housekeeper (Rosa Vega), headless at 390 px on `/workspace`: Claim → Start → Can't complete with reason;
   badge shown; no review button for her; no overflow; no failed API calls (`01`).
3. Refusals: demo nurse and demo maintenance — escalate 403, start 403.
4. Typed Aria rt_vozelx5x_1791792483227: "It's still open, and staff weren't able to finish it, so a supervisor has
   been asked to look at it."
5. Owner in Claude Chrome (Admin → Housekeeping, desktop): Mark reviewed with a note, then "Assign to" → Demo - Rosa
   Vega ("Done"; `02`).
6. Housekeeper started and completed it.

Receipts, one workflow id: resident_request_created → task_assigned (acts_for:housekeeping) → task_in_progress →
task_escalated (assignee) → task_reviewed (admin_override:owner) → task_assigned (admin_override:owner) →
task_in_progress → task_completed; every history entry carries its receipt id.
Counts: housekeeping board open 4 = the 4 older records the queue hides; completed today 1.

Gates: backend unchanged since `e2a8770` (593/0/31); frontend 88 suites / 631; build compiled. Production
unchanged (`ff87c22`). Limits: as for Nursing — supervisor = owner/admin; unclaimed auto-flag is Nursing only.
