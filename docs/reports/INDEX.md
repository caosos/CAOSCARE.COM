# Reports Index

Start here. Updated by Claude Code and ChatGPT-Aria as shared project state changes — this is the fastest way to reconstruct current CAOSCARE state without asking Michael to relay prior conversations.

_Last updated: 2026-08-23_

## Current working directive
[CURRENT_DIRECTIVE.md](CURRENT_DIRECTIVE.md)
— Shared standing instructions: EliteDesk + GitHub workflow, Voice-first priority, browser-visible acceptance, ~30-minute milestone commit/push cadence, safe synchronization, and ~300-line/no-God-file architecture rule.

## Admin / community product blueprint
[ADMIN_PRODUCT_BLUEPRINT.md](ADMIN_PRODUCT_BLUEPRINT.md)
— Governing map for CAOSCARE as a building operating system: company → community/facility → departments/staff/front desk → residents/rooms/devices → requests/tasks/scheduling/transportation/activities/menus/reports. Includes target navigation, department workspaces, staff access, Front Desk, dated calendars, transportation process, and onboarding prerequisites.

## Latest forensic report
[2026-08-23-1448-room304-morning-forensics.md](2026-08-23-1448-room304-morning-forensics.md)
— Chauncey/Room 304 morning session. `mark_resting` misfired on a non-dismissal phrase; a ~20s period with zero detected speech followed, cause unproven.

## Latest acceptance-test status
No clean Voice acceptance pass yet.

A newer live resident-room test reproduced a listening-but-deaf state while the UI continued showing `LIVE · IDLE` / "Speak any time — I'm listening." The visible user transcript also did not semantically match Aria's response. Claude needs to locate and forensically report that newest session before tuning more Voice variables.

## Latest local-dev-outage report
[2026-08-23-2008-local-dev-connectivity-outage.md](2026-08-23-2008-local-dev-connectivity-outage.md)
— **RESOLVED.** Two distinct IPv6/IPv4 `localhost` connectivity mismatches; never data loss. Frontend/backend connectivity was corrected and the frontend dev process is supervised persistently.

## Latest deployment report
[2026-08-23-1913-production-deployment-inspection-and-design.md](2026-08-23-1913-production-deployment-inspection-and-design.md)
— Historical/read-only production inspection and deployment design. Public/Linode deployment is currently out of scope.

## Current unresolved issues

### Voice
- Listening-but-deaf failure remains active; newest session needs forensic reconstruction.
- Mic/audio-path instrumentation may still be insufficient to prove resident-silent vs resident-speaking-but-not-detected.
- `mark_resting` still requires a code-level intent gate.
- Short echo/phantom turns remain a known failure mode.
- `server_vad` remains the baseline; prior `semantic_vad` eagerness `low` experiment caused a 38s detection dead zone and was reverted.
- Visible transcription and native Realtime audio understanding can diverge; operational truth/provenance must remain guarded.

### Admin / operating model
- Admin information architecture is being consolidated under `ADMIN_PRODUCT_BLUEPRINT.md`.
- Company/community/facility onboarding and prerequisite hierarchy need to be audited; downstream objects should not pretend to be configured without a real community/facility.
- Departments are currently registry rows rather than clickable operational workspaces.
- Staff access/onboarding and a first-class Front Desk module need coherent end-to-end workflows.
- Scheduling and transportation calendars need actual dated/day-clickable views and understandable status progression.

### Architecture debt
- `backend/models.py` remains oversized temporary technical debt and must be split by coherent domain responsibility in a dedicated round. The prior exception is not permanent precedent.

## Current system state
See [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md) for the dated implementation log. For current marching orders, prefer `CURRENT_DIRECTIVE.md`; for Admin/product structure, prefer `ADMIN_PRODUCT_BLUEPRINT.md`.
