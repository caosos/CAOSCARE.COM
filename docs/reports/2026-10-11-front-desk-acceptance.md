# Front desk normal-work browser acceptance (front-desk role) — 2026-10-11

Scope: the living checklist item "Browser acceptance by a front-desk role and an administrator" under
*Front desk and administrative communication*. This report covers the **front-desk role half**. The
administrator half was not run (see *Not covered*).

## Setup (silent, isolated from the owner's browser)
- Dev stack on the EliteDesk: frontend `localhost:3000` (dev server, proxies `/api`) → backend `:8092`
  (pid 263725, product code `dc2e4ca` = release candidate `ff87c22` minus docs-only commits), dev DB `caoscare`.
- Headless Chrome via Playwright (`channel="chrome"`), fresh browser contexts at 1280×900 and 390×844.
  No microphone, no speakers, no Aria session, the owner's Chrome untouched.
- Signed in as the existing seeded account **Demo - Dana Frost** (`front_desk`) through the normal
  `POST /api/auth/login`; the session token was injected into `localStorage` for the headless contexts only.
- Synthetic data only: resident "Demo - Pearl Nakagawa" (room 3W09); new request titled
  `Demo - FD acceptance <hhmmss>: callback about weekend visitor parking`.
- Script: `fd_acceptance.py` (session scratch; records every `/api/` response ≥ 400, console errors, page errors).

## Cases (18 / 18 pass, 0 failed API calls, 0 console errors, 0 page errors)
| # | Case | Result |
|---|------|--------|
| 1 | `/front-desk` at 1280 loads the Administration queue ("Front desk requests") | PASS |
| 2–5 | Tabs Transportation, Ride log, Residents, All requests render, 0 failed API calls | PASS |
| 6 | **New request** → choose resident, Department (default Administration), summary, exact words → *Send request* → toast "Request sent to the department" → card appears in Unassigned | PASS (`task_e0fc6d7a7bbf`) |
| 7 | New card shows *Resident said: "…"* and *not yet acknowledged* | PASS |
| 8 | **Acknowledge** → card shows *seen by Demo - Dana Frost* | PASS |
| 9 | **Claim** → card shows assignee *→ Demo - Dana Frost* | PASS |
| 10 | **Start** → status IN PROGRESS | PASS |
| 11 | **Note** → *Save note* → "Note saved", note shown on the card | PASS |
| 12 | **Complete** (with outcome text) → listed under *Recently completed* | PASS |
| 13 | **History** opens the Request history dialog with the full timeline (created / acknowledged / claimed / started / note / note / completed) | PASS |
| 14 | `GET /api/tasks/{id}/detail` as the front-desk user: status `completed`, 6 receipts | PASS |
| 15 | `/front-desk` at 390 loads, `scrollWidth` = 390 (no horizontal overflow) | PASS |
| 16–18 | 390 tabs Transportation, Residents, All requests: no overflow | PASS |

Duplicate detection was also exercised unintentionally: a second submission for the same resident while
her first request was still open returned the *re-request* toast and folded into the existing request
(`task_fc580fd9dc9d`, `re_request_count` 1) instead of creating a second one. That earlier request was then
taken through the same lifecycle and completed.

## Receipt chain of `task_e0fc6d7a7bbf` (from `/tasks/{id}/detail`)
Every receipt carries `actor_type: real-human`, `actor_role: front_desk`, `actor_name: Demo - Dana Frost`,
`before_state` / `after_state`, and a link to the previous receipt:

| action_type | authority | channel | previous |
|---|---|---|---|
| resident_request_created | front_desk_entry | front_desk | — |
| task_acknowledged | acts_for:administration | staff_ui | rcpt_09e882d7f341 |
| task_assigned | acts_for:administration | staff_ui | rcpt_472a862ef4d3 |
| task_in_progress | assignee | staff_ui | rcpt_c14c77629f7b |
| task_note_added | assignee | staff_ui | rcpt_11433645e2e5 |
| task_completed | assignee | staff_ui | rcpt_227cfab6cec6 |

## Screenshots (`docs/reports/assets/2026-10-11-front-desk/`)
`01_front_desk_1280`, `02_tab_{transport,ridelog,residents,all}_1280`, `03_new_request_form_1280`,
`04_queue_after_create_1280`, `05_card_in_progress_1280` (assignee, note, Complete/Note/History actions),
`06_history_dialog_1280` (timeline + "RECEIPTS (6)"), `07_front_desk_390`, `08_new_request_form_390`.

## Observations (not defects in the product path under test)
- The dev DB's Administration queue still lists old `TEST-ISOLATION-40x` tasks (2026-08-29) and MOCK
  residents' requests; they are test leftovers, visible to real front-desk staff on the dev stack.
- "Reassign" exists as the per-card *Assign to…* select (front desk `adminMode`); there is no *reopen*
  action for a completed request in this workspace (checklist wording "close/reopen" is not fully met).
- The completion outcome text is recorded as a `task_note_added`-style history line plus the
  `task_completed` receipt (two lines at the same second in History); consistent, slightly redundant.

## Not covered
- **Administrator half.** No admin login exists for the dev stack except the owner's account and a bring-up
  fixture whose credential is unknown. Creating a temporary labelled demo admin from the coordinator session
  was refused by the session's permission classifier (privilege grant), so the admin pass
  (`/admin?tab=requests|tasks|communications|staff`) was not run. NEED: Michael either signs in as owner at
  `localhost:3000` in his Chrome (then the admin pass can be driven there), or runs the one-line temp-admin
  creation himself, or adds a permission rule.
- Family-/resident-facing status (Aria read-back of this request) was not exercised; silent run.
- Not deployed, not run against production. Demo request records remain in the dev DB (labelled "Demo -").
