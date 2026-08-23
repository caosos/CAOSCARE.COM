# Admin visual acceptance gap report — 2026-08-23

Consolidated inspection of all 9 screenshots Michael uploaded as visual
acceptance evidence, reconciled against `ADMIN_PRODUCT_BLUEPRINT.md` and
`CURRENT_DIRECTIVE.md`. Per the intake file, these screenshots are
authoritative for what Michael actually sees — database/API state is not
treated as proof of a UI pass anywhere in this report. No code was
changed producing this report; it is inspection only, as instructed.

Screenshots now live at
`docs/reports/screenshots/2026-08-23-admin-review/`, moved with `git mv`
(history preserved, confirmed as renames not new files).

## Important correction on the residents-count complaint

Michael's complaint was "only 1-7 residents visible, not ten or
fourteen." **The screenshots themselves do not reproduce that.**
`Screenshot ...15-52-15.png` and `...15-53-37.png` both clearly show
**"Residents (17)"** in the tab count, with MOCK Clarence, MOCK Dorothy,
MOCK Eleanor, MOCK Harold, MOCK Margaret, and MOCK Patricia all visibly
listed and rendered correctly.

This is not being used to dismiss the complaint. The most likely honest
explanation: Michael looked at the page *before* it had reloaded against
the freshly-restarted/seeded backend (this session has already proven,
twice tonight, that a stale unrefreshed page is a real, recurring failure
mode here), and by the time he captured proof, a refresh had already
caught it up. If the resident count looks wrong again, the first thing to
check is staleness/refresh, not the data layer — the data layer is
confirmed correct both in the database and, per these screenshots, in
the rendered UI.

That said, the screenshots surfaced something **more severe** than a
residents count: **no facility/community record exists at all.**

## Gap table

| # | Screenshot | Screen/tab | Classification | What Michael can do | What backend claims | Gap | Blueprint expectation | Smallest repair |
|---|---|---|---|---|---|---|---|---|
| 1 | `15-57-34` | Facility & Staff → Facilities | **BROKEN / MISSING (severe)** | Sees "No facilities yet. Add the first one to start scoping data." | 17 residents, 8 departments, 52 requests, menu, schedule all exist and are being displayed elsewhere in the same session | The entire hierarchy blueprint §1 requires Company → Community/Facility to exist *before* downstream objects. Here every downstream object exists and renders while the facility itself does not. Nothing in the UI treats this as a problem — no onboarding prompt, no warning banner. | "The application must not behave as though a community exists when none has been created." | Do **not** silently seed a fake facility. Surface this honestly: add a setup banner/onboarding gate when `Facilities` is empty, on the main Community administration screen, not buried inside Facility & Staff → Facilities. This is the single highest-priority Admin gap. |
| 2 | `15-54-24` | Communication & Requests → Departments | **PARTIAL / WRONG LOCATION** | See name/contact/status, toggle-delete only | 8 departments, each with real routed requests (confirmed: 52 mock_seed tasks across 9 categories) | Departments is a registry, not a workspace — clicking a row does nothing. Also two levels deep (top-tab → sub-tab) instead of its own top-level nav item. | §5: department workspace should show staff, routed requests, workload, aging, schedule. §4: Departments & Staff should be the **first** top-level nav item. | Make each department row a link into a workspace view (start with: open requests count + list, filtered from the same `staff_tasks` data already flowing). Nav reorder is a separate, larger change — flag, don't do yet. |
| 3 | `15-55-14`, `15-55-20` | Communication & Requests → Transportation | **PARTIAL / NOT UNDERSTANDABLE FROM UI** | See 10 real inbound requests (401-410, real purposes/dates), all "Pending — no slot yet", no click-through visible | Real `TransportSlot`/booking engine exists per `transportation_engine.py` | Every request is stuck in the same terminal-looking state with no visible action to actually schedule it. | §11: must distinguish requested / pending scheduling / scheduled / driver assigned / etc., each with an understandable next step. | Add a visible "Assign slot" / "Schedule" action per pending row — even a minimal version unblocks the biggest confusion. |
| 4 | `15-54-40` | Communication & Requests → Transport resources | **MISSING (data)** | Sees empty Drivers and Vehicles tables | 10 transportation requests exist and are unfulfillable | Zero drivers, zero vehicles configured — the pending requests above **cannot** be resolved even if a "schedule" action existed, because there's nothing to assign. Correctly does not fabricate fake capacity (good — matches blueprint's "do not invent capacity" rule), but the empty state doesn't explain *why* everything is stuck. | §11 Resources section. | Add real drivers/vehicles (Michael's call whether mock or real), and/or surface "0 drivers configured" as the reason pending requests can't move, right on the Transportation screen itself, not just the empty Resources tab. |
| 5 | `15-56-06` | Facility & Staff → Staff | **PARTIAL** | Sees a flat 2-row table (Michael/owner, one TEST User/staff), reset-password/delete only | — | No department assignment shown per staff row, no invite flow visible, no role variety, no way to see who's assigned where. | §6: real invite/role/department lifecycle. | Out of scope for this pass — flagged for the dedicated Facility & Staff round per the blueprint's own phasing. |
| 6 | `15-56-06` | Facility & Staff → Zones | **MISSING (data)** | "Zones (0)" | — | No zones configured at all. | §12 facility config should include rooms/zones/floors. | Flag only; depends on facility existing first (see #1). |
| 7 | all | Top nav (Residents & Care / Communication & Requests / Facility & Staff / Devices & Hardware / Reports) | **WRONG LOCATION / WRONG IA** | Navigates via 5 top tabs, Reports included as its own top-level slot | — | Current order does not match blueprint target (`Departments & Staff → Residents & Care → Communication & Requests → Schedules & Transportation → Devices & Hardware`); Departments isn't even a top-level tab; Reports occupies a scarce top-level slot the blueprint says it shouldn't. | §4. | This is the largest, most disruptive single change in this report (touches primary navigation). Explicitly **not** doing this now — flagging it as the top structural item for a dedicated, coherent navigation-restructure milestone, not a drive-by edit. |
| 8 | `15-52-15`, `15-53-37` | Residents & Care → Residents | **WORKING** | Sees all 17 residents including the 10 MOCK ones, correct data, Enter room/Brief/Resident Record/Memory/Movement/Edit all present per row | 17 residents in Mongo | None found in this evidence | §8 | No repair needed. Keep as the reference example of what "working" looks like in this audit. |
| 9 | `15-52-07` | Public landing page | **WORKING** | Sees marketing page, Launch kiosk demo / Continue to admin | — | None | n/a (outside blueprint scope) | No repair needed. |

## Priority ranking (for the next Admin milestone, after Voice)

1. **Facility/community does not exist** (#1) — the structural root of the hierarchy, blocks everything else in the blueprint's own logic being *true* rather than just *displayed*.
2. **Departments as real workspaces** (#2) — directly requested, directly blocks "departments actively engaging" being verifiable from the UI.
3. **Transportation's stuck "no slot yet" state + empty resources** (#3, #4) — the two are the same underlying gap (no driver/vehicle to assign) and should be fixed together.
4. Staff lifecycle (#5) and Zones (#6) — smaller, can follow.
5. Top-level navigation restructure (#7) — largest single change, deliberately last: it's disruptive and cuts across everything else, better done once the workspace content it needs to route to actually exists.

## What this report deliberately does not do

Per Michael's explicit instruction, this is inspection only. No Admin
code was changed producing this report, and Voice remains the standing
priority per `CURRENT_DIRECTIVE.md` unless Michael says otherwise. This
report exists so the next Admin engineering block (whenever Michael
calls it) executes against a real map instead of another disconnected
feature.
