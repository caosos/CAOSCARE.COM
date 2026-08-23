# Admin visual acceptance intake — 2026-08-23

Michael uploaded a set of live Admin UI screenshots directly to the repository root as acceptance evidence.

These screenshots are authoritative for what Michael actually sees. Database counts, seed-script counts, or backend rows do not constitute a UI pass if the corresponding information is not visible, understandable, and operable from the Admin interface.

## Uploaded screenshots currently in repo root

- `Screenshot from 2026-08-23 15-52-07.png`
- `Screenshot from 2026-08-23 15-52-15.png`
- `Screenshot from 2026-08-23 15-53-37.png`
- `Screenshot from 2026-08-23 15-54-24.png`
- `Screenshot from 2026-08-23 15-54-40.png`
- `Screenshot from 2026-08-23 15-55-14.png`
- `Screenshot from 2026-08-23 15-55-20.png`
- `Screenshot from 2026-08-23 15-56-06.png`
- `Screenshot from 2026-08-23 15-57-34.png`

Claude Code should verify the exact root screenshot set before moving anything, because Michael may add more images.

## Required handling

1. On the EliteDesk, fetch/fast-forward safely from `origin/main` only if the worktree permits it.
2. Treat every root-level `Screenshot from 2026-08-23 *.png` as visual acceptance evidence, not junk.
3. Move the screenshots with Git history preserved into a clear folder such as:
   `docs/reports/screenshots/2026-08-23-admin-review/`
4. Do not delete any screenshot without preserving it in that evidence folder.
5. Inspect each screenshot visually and correlate it with the actual Admin code and APIs.
6. Reconcile the screenshots against `docs/reports/ADMIN_PRODUCT_BLUEPRINT.md` and `docs/reports/CURRENT_DIRECTIVE.md`.
7. Produce one consolidated visual-gap report before making broad Admin changes.

## Gap report format

For every major visible Admin area, classify:

- WORKING
- PARTIAL
- BROKEN
- MISSING
- WRONG LOCATION / WRONG INFORMATION ARCHITECTURE
- NOT UNDERSTANDABLE FROM UI

For each discrepancy record:

- screenshot filename
- visible screen/tab
- what Michael can actually do
- what the backend/database claims exists
- what is missing or confusing in the UI
- blueprint expectation
- smallest coherent repair

## Current product-direction observations from Michael

These are requirements to reconcile against the screenshots, not optional styling suggestions:

- The normal Admin workspace is for **one community/facility**, not a corporate surveillance dashboard across every community.
- A company/organization and then a community/facility must exist before downstream operational configuration makes sense.
- Departments should be a primary operating area, not buried inside Communication & Requests.
- Preferred top-level direction begins with **Departments**, then **Residents & Care**, then **Communication & Requests**, with remaining areas organized by operational meaning.
- Reports can live within an appropriate operational/reporting area instead of occupying valuable primary navigation if that improves the map.
- Departments must be real clickable workspaces, not rows that can only be created, toggled, or deleted.
- Department workspaces should expose their people, routed requests/tasks, status/workload, schedules/coverage where applicable, and operational configuration.
- Facility & Staff conceptually belongs with community/department administration; staff access must have a real invite/login/role/department lifecycle.
- A first-class **Front Desk** module is required because CAOSCARE is intended to help run the building.
- Transportation must expose an understandable process from request through scheduling/assignment/completion; `pending / not slotted yet` needs an obvious next action/process.
- Transportation calendar must be a real date-oriented calendar: show actual days/dates, click a day, see that day's scheduled transportation and related details.
- The system must not treat seeded backend data as a success when the operator cannot find or use it in the UI.

## Scope discipline

Do not respond to these screenshots by independently building another unrelated Admin tab.

First map the current UI against the governing blueprint and produce one gap inventory. Then implement coherent slices from that map.

Voice remains the immediate reliability priority unless Michael explicitly tells Claude to switch the active engineering block, but this visual acceptance report must govern subsequent Admin/scheduling work so the product stops growing willy-nilly.

## Standing engineering rules

- approximately 30-minute tested milestone -> commit -> push cadence
- GitHub is the canonical shared state layer
- EliteDesk is the active development machine
- handwritten production code normally stays around/under 300 lines
- no God files; split by coherent responsibility
- inspect before mutating; preserve evidence
