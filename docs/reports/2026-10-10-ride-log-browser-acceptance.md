# Ride log browser check — 2026-10-10 (staging, synthetic data)

Commit under test: `849eb0a` (CSV neutralization, date validation, truncation flag, stale-response guard). Stack: scratch DB `caoscare_ridelog_stage` (seeded with 4 synthetic users, 1 driver, 1 van, 1 run, 6 rides; no real residents), backend :8131, a production `yarn build` served by `room-node/aria_wake/serve_built.js` on :3133, headless Chrome driven over CDP (script not kept in the repo). Voice/Room 214 not touched. Providers blank.

## Observed
| Check | Result |
|---|---|
| Admin → Communication & requests → Ride log, 2031-03-10 | 6 rides, counts Waiting 3 / Booked 1 / On the road 0 / Completed 1 / Cancelled 1; booked row shows pickup 08:30, Driver Dana, Van 1 |
| Status filter "cancelled" | only `s_cancel` shown |
| Row click | shared history dialog: note "resident feels better", "Created (front desk)" |
| CSV (same request the button makes) | one row per ride; `=HYPERLINK(...)` and `+1+1` come out as `'=HYPERLINK(...)`, `'+1+1`; plain `Mary O'Neil - Room 4` and `"Dr. Smith, 9:30; bring cane"` untouched |
| API status | admin 200, front desk 200, nurse 403, resident 403, anonymous 401 |
| Front desk page → Ride log tab | renders |
| Nurse opening the admin Ride log URL | redirected to /staff, no log |
| Anonymous opening it | redirected to /admin-login, no log |
| Phone width 390 px | 0 px horizontal overflow |

Screenshots: `docs/reports/assets/2026-10-10-ride-log/` (admin log, history dialog, front desk tab, phone).

## Not verified here
- The stale-response guard is covered by a unit test of the helper only; no real slow-network reproduction in a browser.
- Truncation (>5000 rides) not exercised in the browser (backend test with a lowered cap only).
- Real rides need real drivers and vehicles (owner). Repeated navigation/rapid filter changes were not scripted beyond the sequence above.

## Update — remaining bounded cases (commit 6caa8f6; same isolated stack, 5,200 extra synthetic rides on 2031-04-01)
| Case | Result |
|---|---|
| >5000 rides, real list | 5000 rows shown with the visible notice "More than 5000 rides matched; narrow the range. This list is incomplete." — PASS |
| Real CSV button download, truncated | file saved as `rides-2031-04-01-to-2031-04-01-PARTIAL.csv` (5001 lines = header + 5000) and a warning toast says the export is PARTIAL — PASS (before this fix the download looked complete: fixed by reading `X-Truncated`; CORS now exposes that header) |
| Real CSV button download, small range | `rides-2031-03-10-to-2031-03-10.csv`, no partial notice — PASS |
| Rapid filter, out-of-order replies | the old "cancelled" request was held in the browser (CDP Fetch), filter switched to "completed", old reply released afterwards: screen kept the completed rows only — PASS |
| Repeated navigation (4× away and back) | log renders each time — PASS |
| Valid date filter | exercised in both runs — PASS |
| Screenshots of this second run | NOT CAPTURED (values above are scripted DOM/file observations) |
| A true complete paginated export | NOT BUILT: partial exports are labelled instead; the user must narrow the range |
| Unmount mid-request in a real browser | NOT RUN (covered by the component test only) |

## Update 2 — staff-UI transport lifecycle, EmailReadiness fake states, unmount (da-5f90a99ee6)
Same isolated stack (scratch DB, :8131 backend, built UI via serve_built on :3133, headless Chrome/CDP; fleet = one driver and one van created through the admin API; synthetic resident). Screenshots: `docs/reports/assets/2026-10-10-ride-log/A*.png` (transport) and `B_*.png` (email). No provider key was real; the backend ran with HTTP(S)_PROXY pointed at a local counter: **0 outbound connection attempts** across the four email cases.

### (A) Transport, driven through the real UI
| Case | Result / artifact |
|---|---|
| Front desk "New ride" form (resident, purpose, date, time as said) | PASS — A1, A2 pending card "Needs coordination" |
| Assign dialog → driver/vehicle auto-picked, pickup 08:45 | PASS — A3, A4 run card "Pickup 08:45 · Confirmed · Dana Driver · Van 1" |
| Transportation staff: Departed then Ride completed | PASS — A5, A6; depart button gone after depart, both gone after complete |
| Same task id in Ride log, history, real CSV button | PASS — A7 (one row, Completed), A8 (Created, Booked by Fran Desk, Departed by Tran Sport, Completed, 5 receipts), CSV file contains the task id with status `completed` |
| Second completion (run endpoint and task endpoint) | PASS — both HTTP 400; receipts show a single `transportation_completed` plus `task_complete_refused` |
| Change time via the rider's edit button | PASS — new run 11:15 booked |
| **Cancelled old run still listed the moved ride as "Booked" with cancel/history buttons (A9)** | **FAIL (found)** — fixed: calendar only lists a rider on the run its task currently belongs to (`transportation_calendar.py`); assertion added to `test_transportation_lifecycle.py` (fails on the old code, passes now). A9 is the BEFORE picture; the cancelled 10:00 card itself is still displayed (struck, empty) |
| Cancel with reason | PASS — A10 log row "Cancelled" |
### (B) EmailReadiness (admin → Email & notifications), fake env values
| Case | Observed |
|---|---|
| nothing configured | key, sender, webhook secret, department inboxes, both inbound senders show "Not set"; domain-verified and webhook-reachable show **Unknown**; header says configuration incomplete — PASS (B_missing.png) |
| default sender `onboarding@resend.dev` | sender row badge "Resend default address" — PASS (B_default.png) |
| invalid sender "not an address" | badge "Invalid address" — PASS (B_invalid.png) |
| fully fake-configured | no "Not set"/default/invalid badges; domain and webhook still **Unknown**; text says it does not mean email works — PASS (B_configured.png) |
| role gating | API: admin 200, front desk 403, nurse 403, anonymous 401; front desk opening the admin URL is redirected away (no panel) — PASS |
### (C) Ride log unmount mid-request
Fixed (an unmount now invalidates in-flight replies) and covered by a component test that fails without the fix. NOT run in a real browser.
### Still NOT RUN / not built
Real browser slow-network repro of the three UI screens; screenshots for the second ride-log run; complete paginated CSV.

## Update 3 — shared staff-workflow defects, real browser with controlled network (da-0c87125243)
Same isolated stack (fresh scratch DB, built UI :3133, headless Chrome/CDP). Network control: CDP `Fetch` pauses, fails or fulfils chosen requests. Synthetic data only: two nursing requests created through the API, no providers. Artifacts: `docs/reports/assets/2026-10-10-ride-log/C*.png`, `A9_after_fix_moved_ride.png`.
| Case | Result |
|---|---|
| DepartmentQueue: first completion request fails (network error) | PASS — dialog stays open, typed note "typed note that must survive" kept, submit re-enabled (C1) |
| …retry then succeeds | PASS — dialog closes; the task has exactly **one** `task_completed` receipt (no duplicate) (C1b) |
| History dialog: slow detail reply for task A arrives after task B was opened | PASS — dialog keeps showing B ("beta wants a pillow"), no "alpha" text (C2) |
| History dialog: detail request answered 403 | PASS — recoverable error with "Try again", not stuck on Loading (C3); retry then loads the history |
| Communications log: old "All statuses" reply released after the "Failed" filter result | PASS — list stays failed2@/failed3@ only (C4) |
| Moved ride, calendar AFTER the fix (A9_after_fix) | PASS for the defect: the ride appears exactly once (on the 11:15 run). The cancelled 10:00 run card is still shown, now empty (struck "Cancelled"); not hidden — left as is |
Not rerun: earlier cases. Still NOT RUN: real slow-network browser repro was replaced by controlled interception above; complete paginated CSV (not built); live voice/production (out of scope).
