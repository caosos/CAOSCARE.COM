# Therapy end-to-end acceptance — 2026-10-12

Task `careops-therapy-browser-acceptance-001`. Development stack only (backend `b7f6048`, frontend `db4317f`),
headless Chrome, synthetic data. Script: `assets/2026-10-12-therapy-acceptance/acceptance_run.py`.

## Gap found and repaired (`db4317f`)
The completion note, cancel reason and reopen reason all become the request's latest note, which the resident's
screen shows and Aria reads. Only the plain note dialog said so. The complete, cancel and reopen dialogs now say:
"The resident sees this text on their screen and Aria may read it to them." Two existing queue tests assert the
wording (they fail without it).

## Accounts
Owner (token minted in-process), demo front desk (Dana Frost), demo nurse (Nancy Reyes), and a **temporary
labelled Therapy login** "Demo - Temp Therapist (acceptance)" created through the existing staff API and deleted
at the end. Residents: the synthetic demo-room resident (room DEMO) and demo resident 3W01.

## Results (32/32 pass, no failed API calls)
| # | Criterion | Evidence |
|---|---|---|
| 1 | create | front desk request (authenticated resident-request API) visible on the front desk All requests tab |
| 2 | plan / reschedule with provider, kind, place | therapist Plan dialog: 10:00 AM, then 2:00 PM; card shows provider and Therapy gym |
| 3 | claim / start | therapist clicked Claim and Start; task in progress, assigned to the therapist |
| 4 | operational note | note dialog says the resident hears it; note shown to resident |
| 5 | complete | therapist at 390 px, dialog labelled, completion note saved, no overflow |
| 6 | cancel and reopen | owner reopened (dialog labelled; pending, assignee kept); therapist cancelled a second appointment (dialog labelled) |
| 7 | recurrence + Upcoming | weekly series; one occurrence in the therapist's Upcoming and the resident's upcoming list |
| 8 | cross-resident conflict | Plan for 3W01 at 2:30 PM with the same provider → dialog names the other appointment, room DEMO, "same provider"; nothing written; Save anyway → `task_schedule_updated` receipt `conflict_override`, `acts_for:therapy`; Upcoming shows the overlap |
| 9 | linked transportation | therapist clicked Ride; one linked ride request |
| 10 | receipt / history chain | one workflow id: created → details → schedule ×2 → assigned → in_progress → note → ride_requested → completed → reopened; every history entry has a receipt id |
| 11 | refusals + clinical field | nurse plan 403, nurse detail 404, front desk start 403, therapist inspect 403, `diagnosis` 422 |
| 12 | resident-safe truth | resident Home at 1280 and 390 shows window, provider, note; status endpoint Aria uses says "working on it", window, provider, latest note; resident upcoming carries no conflicts |

Screenshots: `01-frontdesk`, `02a/02b-therapist`, `03-resident-1280/390`, `04-therapist-complete-390`,
`05-owner-reopen`, `06-conflict-dialog`, `07-upcoming`, `08-history`.

## Cleanup
All synthetic requests (including the ride and the recurring occurrence), the series and the temporary account
were deleted through the API; a follow-up query found none left.

## Gates
Backend 603 passed / 0 failed / 31 skipped at `b7f6048` (no backend change since). Frontend 90 suites / 642; build compiled.

## Limits
- Aria was checked through the same status/upcoming endpoints its tools call, not a live voice/Realtime call.
- The resident room screen at 390 px still overflows sideways by ~200 px (the kiosk accessibility row; pre-existing,
  not Therapy).
- Front-desk creation used the authenticated API, then the front desk UI; the New request form itself was accepted
  on 2026-10-11.
- Production `ff87c22` unchanged.
