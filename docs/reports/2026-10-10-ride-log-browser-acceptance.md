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
