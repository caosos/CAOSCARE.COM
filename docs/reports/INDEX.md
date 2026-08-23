# Reports Index

Start here. Updated by Claude Code and ChatGPT-Aria as shared project state changes — this is the fastest way to reconstruct current CAOSCARE state without asking Michael to relay prior conversations.

_Last updated: 2026-08-23_

## Current working directive
[CURRENT_DIRECTIVE.md](CURRENT_DIRECTIVE.md)
— Shared standing instructions: EliteDesk + GitHub workflow, Voice-first fundamentals/regression priority, parallel non-overlapping agent lanes, browser-visible acceptance, ~30-minute milestone commit/push cadence, safe synchronization, and ~300-line/no-God-file architecture rule.

## Multi-agent execution plan
[MULTI_AGENT_EXECUTION_PLAN.md](MULTI_AGENT_EXECUTION_PLAN.md)
— Standing parallel-work model. Multiple agents work simultaneously on different, explicitly owned domains using isolated worktrees/branches, with one lead/integration agent protecting the primary tree. Current lanes: Voice fundamentals/regression hunt; Community/Admin operating model + visual acceptance; Scheduling/calendars/transportation; QA/architecture/integration review. No two agents race on the same production files.

## Admin / community product blueprint
[ADMIN_PRODUCT_BLUEPRINT.md](ADMIN_PRODUCT_BLUEPRINT.md)
— Governing map for CAOSCARE as a building operating system: company → community/facility → departments/staff/front desk → residents/rooms/devices → requests/tasks/scheduling/transportation/activities/menus/reports. Includes target navigation, department workspaces, staff access, Front Desk, dated calendars, transportation process, and onboarding prerequisites.

## Admin visual acceptance evidence
[2026-08-23-admin-visual-acceptance-intake.md](2026-08-23-admin-visual-acceptance-intake.md) (intake) →
[2026-08-23-admin-visual-gap-report.md](2026-08-23-admin-visual-gap-report.md) (**consolidated gap report, done**)
— Screenshots moved to `docs/reports/screenshots/2026-08-23-admin-review/` with git history preserved. Top finding: **no facility/community record exists at all** ("No facilities yet") even though residents/departments/requests/menu/schedule all render — the real structural gap, more severe than the residents-count complaint, which does not reproduce in the screenshots themselves (they show all 17 residents correctly, including the 10 mocks — most likely a stale-page moment when Michael first looked). Departments confirmed still a registry, not a workspace. Transportation stuck at "Pending — no slot yet" with zero drivers/vehicles configured. Full priority ranking in the report. No Admin code changed yet — inspection only, per instruction.

## Latest forensic report
[2026-08-23-1448-room304-morning-forensics.md](2026-08-23-1448-room304-morning-forensics.md)
— Chauncey/Room 304 morning session. `mark_resting` misfired on a non-dismissal phrase; a ~20s period with zero detected speech followed, cause unproven.

## Latest acceptance-test status
No clean Voice acceptance pass yet.

A newer live resident-room test reproduced a listening-but-deaf state while the UI continued showing `LIVE · IDLE` / "Speak any time — I'm listening." The visible user transcript also did not semantically match Aria's response. Voice work is now explicitly a **fundamentals/regression hunt**: identify the earlier reliable baseline, compare it with current, instrument missing boundaries, and A/B a minimal baseline if useful before more tuning.

## Latest local-dev-outage report
[2026-08-23-2008-local-dev-connectivity-outage.md](2026-08-23-2008-local-dev-connectivity-outage.md)
— **RESOLVED.** Two distinct IPv6/IPv4 `localhost` connectivity mismatches; never data loss. Frontend/backend connectivity was corrected and the frontend dev process is supervised persistently.

## Latest deployment report
[2026-08-23-1913-production-deployment-inspection-and-design.md](2026-08-23-1913-production-deployment-inspection-and-design.md)
— Historical/read-only production inspection and deployment design. Public/Linode deployment is currently out of scope.

## Current unresolved issues

### Voice
- Listening-but-deaf failure remains active; newest session needs forensic reconstruction.
- Need historical regression comparison against the simpler early Voice implementation that behaved better.
- Mic/audio-path instrumentation may still be insufficient to prove resident-silent vs resident-speaking-but-not-detected.
- `mark_resting` still requires a code-level intent gate.
- Short echo/phantom turns remain a known failure mode.
- `server_vad` remains the baseline; prior `semantic_vad` eagerness `low` experiment caused a 38s detection dead zone and was reverted.
- Visible transcription and native Realtime audio understanding can diverge; operational truth/provenance must remain guarded.

### Admin / operating model
- **Facility onboarding banner shipped** (`f092ae5`..`bfbec64`) - Community administration screen now shows a clear "Set up your community" action when zero facilities exist, instead of silently rendering as if one does. Backend facility CRUD was already working; the gap was pure UX/IA.
- **Departments are now clickable workspaces** (first pass) - opens a dialog with open/completed/skipped counts and the live routed-request list, reusing existing `/tasks?visibility_role=` data.
- **Transportation "Pending - no slot yet" now has a real Assign action** on both the report and calendar views, reusing the existing booking engine; honestly reports "not configured yet" rather than faking a booking (0 drivers/0 vehicles currently exist). A real pre-existing bug (booked-status only checking the legacy field) was found and fixed along the way.
- Still open: top-level nav restructure, staff invite/role lifecycle, Zones, ScheduleTab's calendar-grid view and its missing email-ingestion UI trigger, and actually configuring real drivers/vehicles so Assign has something to book.

### Architecture debt
- `backend/models.py` remains oversized temporary technical debt and must be split by coherent domain responsibility in a dedicated round. The prior exception is not permanent precedent.
- Do not run that broad split concurrently with active Voice/Admin/Scheduling implementation lanes unless the lead schedules a dedicated integration window.

## Current system state
See [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md) for the dated implementation log. For current marching orders, prefer `CURRENT_DIRECTIVE.md`; for parallel execution rules, `MULTI_AGENT_EXECUTION_PLAN.md`; for Admin/product structure, `ADMIN_PRODUCT_BLUEPRINT.md`.
