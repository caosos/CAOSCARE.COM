# Front desk callback loop — browser acceptance (careops-frontdesk-callback-001) — 2026-10-11

Dispatch (#129 comment 6107540533): with labelled synthetic data and a front-desk role, create one resident callback,
route it to one department, assign/reassign, add a note, complete, explicitly reopen once, and verify responsive history
plus the linked receipt chain. Reuse canonical StaffTask/Receipt records; no new callback data universe.

## Setup (silent, isolated from the owner's browser)
- Dev stack: frontend `localhost:3000` (dev server) → backend `:8092` on integration `ce6c10b` (pid 401682, restarted earlier
  today for the reopen feature `04cc580`), dev DB `caoscare`.
- Headless Chrome via Playwright (`channel="chrome"`), fresh contexts at 1280×900 and 390×844; no microphone, no Aria session.
- Accounts: the seeded `Demo - Dana Frost` (`front_desk`) for the browser, `Demo - Carl Boone` (`staff`, maintenance) for API
  checks; both through the normal `POST /api/auth/login`. Residents `Demo - Alice Monroe` and `Demo - Frank Delgado`.
- Script `fd_callback_acceptance.py` (session scratch; records every `/api/` response ≥ 400, console errors, page errors).
  It first closes any open "Demo callback" left by an earlier run through the normal complete path, because an open one makes
  a new callback for the same resident a re-request (correct dedup, observed on the first rerun).

## Result: 19 / 19 cases, 0 failed API calls, 0 console errors, 0 page errors (task `task_c56f262a2156`, maintenance `task_c2eb5e13c051`)
| # | Case | Result |
|---|---|---|
| 1 | New request → Alice Monroe → Department Administration (default) → callback text + exact words → "Request sent" → task `visibility_role administration`, `source front_desk` | PASS |
| 2 | **Assign** via the card's Assign select → assignee Dana Frost | PASS |
| 3 | **Reassign** → Unassigned → card reads "unassigned" | PASS |
| 4 | Administration roster read: 1 person (Dana) — reassigning to a colleague needs a second front-desk account on the dev stack | noted |
| 5 | Claim after unassign → assignee Dana Frost | PASS |
| 6 | Acknowledge, Start, Note ("left a voicemail for Karen at 3 pm") → IN PROGRESS with the note on the card | PASS |
| 7 | Complete with outcome → Recently completed | PASS |
| 8 | **Reopen once** with reason → PENDING, assignee kept, reason as the current note | PASS |
| 9 | History: Created (front desk) → Claimed → Unassigned → Claimed → Acknowledged → Started → Note → Note + Completed → Note + Reopened (each by Dana, timestamped) | PASS |
| 10 | Receipt chain: 9 receipts `resident_request_created → task_assigned → task_unassigned → task_assigned → task_acknowledged → task_in_progress → task_note_added → task_completed → task_reopened`, each parent = previous, one workflow id, every receipt `identity_basis authenticated`, `actor_role front_desk` | PASS |
| 11 | Every `event_log` entry (10) carries its receipt id | PASS |
| 12 | Second completion after the reopen → completed, chain ends `task_reopened → task_completed` | PASS |
| 13 | Second callback for Frank Delgado **routed to Maintenance** from the same form → `visibility_role maintenance` | PASS |
| 14 | Maintenance staff (Carl) sees it in `GET /api/tasks` | PASS |
| 15 | It does not appear in the front desk's Administration queue | PASS |
| 16 | Front desk sees it under **All requests** | PASS |
| 17 | Front desk cannot start it: `POST /tasks/{id}/start` → 403, status still pending | PASS |
| 18 | Maintenance staff can acknowledge it (API) | PASS |
| 19 | 390 px: front desk queue renders, `scrollWidth` = 390 | PASS |

Screenshots (`docs/reports/assets/2026-10-11-front-desk-callback/`): `01_callback_created`, `02_in_progress`, `03_reopened`,
`04_history`, `05_390_queue`, `06_390_history`. The demo callbacks were closed through the normal complete path at the end
(the maintenance one by the maintenance account); records remain in the dev DB, labelled "Demo".

## What was built for this task
Nothing new: every path existed (the reopen was built earlier today as `careops-frontdesk-reopen-001`, `04cc580`). The task is
acceptance evidence only.

## Observations
- Assigning to yourself through the Assign select is recorded and shown as a claim ("Claimed by"), the same as the Claim button.
- Reassignment to another front-desk colleague could not be exercised: the dev stack has one front-desk account and creating
  staff needs an admin sign-in (owner item). The assign/unassign/claim cycle and the department-scope refusal were exercised.
- Not covered: the administrator half of the Front Desk/Admin acceptance (admin sign-in), real notifications (no provider),
  spoken Aria.
