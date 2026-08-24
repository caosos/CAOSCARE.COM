# Reports Index

Start here. Updated by Claude Code and ChatGPT-Aria as shared project state changes — this is the fastest way to reconstruct current CAOSCARE state without asking Michael to relay prior conversations.

_Last updated: 2026-08-23_

## Current working directive
[CURRENT_DIRECTIVE.md](CURRENT_DIRECTIVE.md)
— Shared standing instructions: EliteDesk + GitHub workflow, Voice-first fundamentals/regression priority, parallel non-overlapping agent lanes, browser-visible acceptance, ~30-minute milestone commit/push cadence, safe synchronization, and ~300-line/no-God-file architecture rule.

## Multi-agent execution plan
[MULTI_AGENT_EXECUTION_PLAN.md](MULTI_AGENT_EXECUTION_PLAN.md)
— Standing parallel-work model. Multiple agents work simultaneously on different, explicitly owned domains using isolated worktrees/branches, with one lead/integration agent protecting the primary tree. Current lanes: Voice fundamentals/regression hunt; Community/Admin operating model + visual acceptance; Scheduling/calendars/transportation; QA/architecture/integration review; Clinical/Staff Care app; Running Facility Testbed/Operational Simulation. No two agents race on the same production files.

## Running facility / Care app testbed
[RUNNING_FACILITY_TESTBED.md](RUNNING_FACILITY_TESTBED.md)
— Defines the owner-only Launch/Pause/Resume/Reset demo-facility model, deterministic scenario engine, synthetic but clearly provenanced operational activity, clinician/med-reminder visibility, role-specific staff tablet workflow, safe notification sandboxing, and browser-visible end-to-end acceptance. Michael may use **Care app** as conversational shorthand for CAOSCARE; this is not a repository/product rename unless separately decided.

## Admin / community product blueprint
[ADMIN_PRODUCT_BLUEPRINT.md](ADMIN_PRODUCT_BLUEPRINT.md)
— Governing map for CAOSCARE as a building operating system: company → community/facility → departments/staff/front desk → residents/rooms/devices → requests/tasks/scheduling/transportation/activities/menus/reports. Includes target navigation, department workspaces, staff access, Front Desk, dated calendars, transportation process, and onboarding prerequisites.

## Admin visual acceptance evidence
[2026-08-23-admin-visual-acceptance-intake.md](2026-08-23-admin-visual-acceptance-intake.md) (intake) →
[2026-08-23-admin-visual-gap-report.md](2026-08-23-admin-visual-gap-report.md) (**consolidated gap report, done**)
— Screenshots moved to `docs/reports/screenshots/2026-08-23-admin-review/` with git history preserved. Top finding: **no facility/community record exists at all** ("No facilities yet") even though residents/departments/requests/menu/schedule all render — the real structural gap, more severe than the residents-count complaint, which does not reproduce in the screenshots themselves (they show all 17 residents correctly, including the 10 mocks — most likely a stale-page moment when Michael first looked). Departments confirmed still a registry, not a workspace. Transportation stuck at "Pending — no slot yet" with zero drivers/vehicles configured. Full priority ranking in the report.

## Latest forensic report
[2026-08-24-2337-room404-forensics.md](2026-08-24-2337-room404-forensics.md)
— **Read-only pass for Issue #22 (SIM-6), no code changed.** Room 404 (MOCK Harold Jefferson), 8m11s, 41 turns, zero dead zones under the same `interrupt_response:true`/`far_field`/`silence_duration_ms:1000` config Lane A flagged. Independently reproduces and resident-confirms the echo/trust-boundary defect: 3 fabricated "user" turns in 19s, each a mishearing of Aria's own immediately-preceding words, persisted `trusted:true` — Harold explicitly denied saying two of them, live. Pinpointed the exact code cause in `classifyUserTurn()` (`realtimeMessageHandler.js` lines 43-58): the echo-resemblance check only runs when a turn is BOTH overlapped AND ≤2 words — a 3-word real-time echo and any delayed (post-playback) echo both structurally skip it. Confirms full-duplex mic capture itself works correctly; the gap is turn classification downstream. Confirms no mic-level/RMS telemetry exists to explain Michael's observed self-adjusting input level.

Prior:
[2026-08-23-2046-room121-deadzone-forensics.md](2026-08-23-2046-room121-deadzone-forensics.md)
— **Lane A, evidence-only, no code changed.** New session (michael/Room 121), 83s terminal dead zone, zero tool calls — disproves `mark_resting` as a necessary trigger (widens the Room 304 finding below). Transport/WebRTC healthy throughout; UI state was accurate about itself, wrong about reality. Confirms the visible-transcript-vs-actual-response divergence Michael described: transcript "things everywhere." vs. Aria's correct time-of-day answer, from independent transcription vs. conversational models. Flags a new data-integrity gap: the wrong transcript was persisted as `trusted: true`. Also documents a sibling session where Aria's own delayed greeting echo (5.7s post-response, past the overlap window) was stored as trusted resident speech and answered as if resident-spoken. Prior: [2026-08-23-1448-room304-morning-forensics.md](2026-08-23-1448-room304-morning-forensics.md) (Chauncey/Room 304 — `mark_resting` misfire, ~20s dead zone).

## Voice regression matrix
[2026-08-23-2152-voice-regression-matrix.md](2026-08-23-2152-voice-regression-matrix.md)
— **Lane A's fundamentals-hunt deliverable, evidence-only.** Full EARLY (`dba0499`, 2026-04-24) vs. NOW input-path comparison across 13 instrumented sessions. Prompt/memory/tool growth (30x, 0→20 tools) explicitly **exonerated** for the deafness regression — all downstream of VAD. Narrowed to 3 input-path deltas: `far_field` noise reduction (upstream of VAD), `silence_duration_ms` doubled to 1000ms, and `interrupt_response: true` (added 08-23, correlates 3/4 deaf sessions vs 1/9, but n=4 and time-confounded). VAD type (server vs semantic) ruled out as differentiator. **Recommended next step, not yet built:** passive `AnalyserNode` RMS mic-level instrumentation (~30 lines) to distinguish "resident silent" from "resident spoke, undetected" before further A/B — current negative results are unfalsifiable without it. If built, proposed single-variable ladder: revert `interrupt_response` first, then `noise_reduction`, then `silence_duration_ms`, testing >=3 real-room minutes between each.

## Latest acceptance-test status
No clean Voice acceptance pass yet.

A newer live resident-room test reproduced a listening-but-deaf state while the UI continued showing `LIVE · IDLE` / "Speak any time — I'm listening." The visible user transcript also did not semantically match Aria's response. Voice work is now explicitly a **fundamentals/regression hunt**: identify the earlier reliable baseline, compare it with current, instrument missing boundaries, and A/B a minimal baseline if useful before more tuning. **Lane A's fundamentals hunt is now complete as an evidence pass** — see regression matrix above; the recommended next action (mic-level instrumentation) has not been built yet.

## Latest local-dev-outage report
[2026-08-23-2008-local-dev-connectivity-outage.md](2026-08-23-2008-local-dev-connectivity-outage.md)
— **RESOLVED.** Two distinct IPv6/IPv4 `localhost` connectivity mismatches; never data loss. Frontend/backend connectivity was corrected and the frontend dev process is supervised persistently.

## Latest deployment report
[2026-08-23-1913-production-deployment-inspection-and-design.md](2026-08-23-1913-production-deployment-inspection-and-design.md)
— Historical/read-only production inspection and deployment design. Public/Linode deployment is currently out of scope.

## Current unresolved issues

### Voice
- Listening-but-deaf failure remains active; newest session (Room 121) forensically reconstructed — 83s terminal dead zone, zero tool calls, transport healthy.
- **Historical regression comparison done** (see Voice regression matrix above): input-path narrowed to 3 candidate deltas (`far_field` NR, `silence_duration_ms: 1000`, `interrupt_response: true`); prompt/memory/tool growth exonerated. `interrupt_response` is the leading hypothesis (H1) but n=4 and time-confounded — not proven.
- Mic/audio-path instrumentation is still insufficient to prove resident-silent vs resident-speaking-but-not-detected — **this is now the explicit blocker before further A/B testing.** Proposed fix (not built): passive `AnalyserNode` RMS mic-level heartbeat, ~30 lines.
- `mark_resting` still requires a code-level intent gate — **confirmed not necessary for the dead-zone failure** (Room 121 went deaf with zero tool calls); remains a real but separate UX defect.
- Short echo/phantom turns remain a known failure mode. **New:** delayed acoustic echo (arriving after `output_audio_buffer.stopped`, past the overlap window) bypasses the trust boundary entirely — a resident session had Aria's own greeting echo back 5.7s later, stored `trusted: true`, and answered as if resident-spoken.
- **New data-integrity gap:** a known-wrong transcript ("things everywhere.") was persisted as `trusted: true` resident memory because `classifyUserTurn()` only measures playback overlap and `transcriptionConfidence()` permanently no-ops (API returns no logprobs on this path). Needs a design decision, not yet a patch.
- `server_vad` remains the baseline; prior `semantic_vad` eagerness `low` experiment caused a 38s detection dead zone and was reverted. VAD type itself is now ruled out as the deafness differentiator — dead zones occurred under both.
- Visible transcription and native Realtime audio understanding can diverge; operational truth/provenance must remain guarded.

### Clinical / Staff Care app
- Existing Clinician Dashboard is primarily analytics/trends/recent events; it is not yet the full clinical operating workspace.
- Existing Medications feature is scheduled resident-room medication reminders + acknowledgment, not a true medication list/eMAR.
- Staff accounts exist, but role/department/tablet daily-workflow integration is incomplete.
- Need clinician resident drilldown, reminder/ack history visibility, relevant appointments/events, and role-specific staff work surfaces without duplicating the facility's authoritative EHR/eMAR.

### Running facility testbed
- Need owner-only Launch/Pause/Resume/Reset demo facility control.
- Need deterministic scenario/event engine that exercises real workflows instead of merely inserting busy-looking database rows.
- Generated records need explicit demo provenance and safe/sandboxed external notifications.
- Browser must visibly show work entering, routing, acknowledging, progressing, completing, and appearing in history across role dashboards.

### Admin / operating model
- **Facility onboarding banner shipped** (`f092ae5`..`bfbec64`) - Community administration screen now shows a clear "Set up your community" action when zero facilities exist, instead of silently rendering as if one does. Backend facility CRUD was already working; the gap was pure UX/IA.
- **Departments are now clickable workspaces** (first pass) - opens a dialog with open/completed/skipped counts and the live routed-request list, reusing existing `/tasks?visibility_role=` data.
- **Transportation "Pending - no slot yet" now has a real Assign action** on both the report and calendar views, reusing the existing booking engine; honestly reports "not configured yet" rather than faking a booking (0 drivers/0 vehicles currently exist). A real pre-existing bug (booked-status only checking the legacy field) was found and fixed along the way.
- Still open: top-level nav restructure, staff invite/role lifecycle, Zones, ScheduleTab's calendar-grid view and its missing email-ingestion UI trigger, and actually configuring real drivers/vehicles so Assign has something to book.

### Architecture debt
- `backend/models.py` remains oversized temporary technical debt and must be split by coherent domain responsibility in a dedicated round. The prior exception is not permanent precedent.
- Do not run that broad split concurrently with active Voice/Admin/Scheduling implementation lanes unless the lead schedules a dedicated integration window.

## Current system state
See [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md) for the dated implementation log. For current marching orders, prefer `CURRENT_DIRECTIVE.md`; for parallel execution rules, `MULTI_AGENT_EXECUTION_PLAN.md`; for Admin/product structure, `ADMIN_PRODUCT_BLUEPRINT.md`; for live-facility simulation/clinical-staff acceptance, `RUNNING_FACILITY_TESTBED.md`.
