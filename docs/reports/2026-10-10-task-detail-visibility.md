# Task detail direct-ID access (da-f9007166dc)

## Policy (source at 5081625)
- List (`routes/tasks.py::list_tasks`): `mine_only` = tasks assigned to the caller (any department); otherwise a `staff` user sees `visibility_role` in [own department, `all_staff`] (no department: `all_staff` only). Owner, admin and front desk are not `staff`, so they see everything. This is unchanged.
- Callers of `GET /tasks/{id}/detail`: `RequestHistoryDialog` (department queues: maintenance, kitchen, activities, housekeeping, front-desk, transportation) and the admin `RequestDetailDialog`. The generic nursing workspace has no History button.

## Root cause
`task_detail.py` required only `get_current_user` and loaded any `task_id`, returning the task (resident words, notes, assignment) and every receipt (actor/authority/provenance) regardless of the list's visibility. Any signed-in staff user who knew an id could read another department's request.

## Fix
`tasks.py::staff_visibility_query(user)` is now the single definition of list scope; `list_tasks` uses it (behaviour identical) and `task_detail` applies the same scope in the query itself, or a task assigned to the caller (the list's `mine_only` path). Authorization happens before any task field or receipt is read. An invisible task answers exactly like a missing one (404 "Task not found"), so existence is not revealed. Owner/admin/front desk unchanged; no role grants added; front-desk and assignment policy not touched. No path disagreed on policy, so no owner choice was needed.

## Evidence
- `backend/tests/test_task_detail_visibility.py` (17 tests, in-process, scratch DB, local-owner bypass off): users owner, admin, front desk, nursing, maintenance, staff without department; tasks nursing, maintenance, all_staff, and a maintenance task assigned to the nurse; two receipts each. Matrix per role; detail never broader than list plus mine_only; denied = same 404 as a nonexistent id, no task/receipt data, task and receipt counts unchanged; allowed keeps receipt order; anonymous 401. 10 of 17 fail on the old route.
- Browser (isolated stack, synthetic data, maintenance staff user; screenshots `assets/2026-10-10-communications-tab/15-17`): History on an own-department task opens (resident words and timeline shown); after the task moved to another department behind a stale list, History shows "Could not load this request's history. Try again" with the dialog itself containing no request data (the list card behind it was loaded earlier and still shows its text); restoring scope and clicking Try again loads the history; a direct fetch of the other department's id returns 404 "Task not found" with no data. Coverage limit: one department queue and one role in the browser; the role matrix is in the backend tests.
- Focused: new + shared_core_history + request_status_lifecycle pass (18 passed, 2 skipped). Full backend gate (port 8128, scratch DB, providers blank): 522 passed, 0 failed, 31 skipped.
