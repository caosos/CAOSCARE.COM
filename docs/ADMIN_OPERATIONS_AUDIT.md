# CAOSCare — Admin / Operations Dashboard Audit

**Date:** 2026-09-06
**Agent/tool:** Claude Code (Sonnet 5), `CAOSCARE-ADMIN` worktree
**Branch/ref:** `claude/admin-operations` @ `d994331` (identical to `origin/main` at audit start)
**Scope:** Forensic audit only. No implementation. Traces UI → API → database for the staff/Admin operational surface: executive/admin dashboard, maintenance, housekeeping, transportation, resident-assistance operations, device/system health, reporting, and role-based experience.
**Out of scope (other Claude's lane, not inspected for change):** RF/pendant matching & debounce, `resident_activation.py`, kiosk wake logic, realtime voice internals, Home Assistant / Midea networking, Room 214 live testing, production/nginx.

A screen existing is **not** treated as "working." Every "working" claim below was traced to a real endpoint and a real collection write/read.

---

## 1. Executive summary

CAOSCare's staff/Admin side is a **broad, shallow tab collection**, not an operations platform. The plumbing that a real operations product needs — a shared task/receipt/event spine, a department routing model, per-resident analytics, an audit export, a transportation resource engine — **already exists and works**. What is missing is the layer on top: **an attention-first overview, first-class department workflows (maintenance/housekeeping), aging/SLA/overdue awareness, and a reporting framework.**

Highest-impact findings:

- **`User.department` is never populated.** No UI or API can set a staff member's department. Every downstream feature that depends on it — department-scoped task visibility, department email notification, the department workspace — silently falls back to "all staff" / "email the admins." The entire "route work to a department" architecture is **inert for line staff today.** (P0)
- **Maintenance and Housekeeping have no data model, no workflow, no module.** They exist only as (a) default department slugs and (b) a `category` string on the generic `StaffTask`. There is no work-order age, priority/safety classification, assignee workflow, activity log, overdue state, repeat-issue detection, vendor/parts/cost, close reason, or preventive-maintenance rounds. (P0)
- **There is no executive/operations dashboard.** `/admin` opens on the "Residents" tab. `/staff` is an alert-only live board. Nothing answers "what needs attention / what's overdue / who owns it / how long has it been open / what's trending / what's offline" across departments. (P0)
- **Auto-escalation does not run.** There is no scheduler. `POST /escalation/tick` (the path that actually notifies a supervisor / on-call) only fires when an admin clicks "Run tick now." A second, disagreeing escalation implementation lives inline in `GET /alerts/feed`. (P1)
- **The generic `Receipt` and `CaosEvent` collections are populated but have no admin UI.** `GET /receipts` and `GET /events` are admin-gated and unused by any dashboard. The richest operational-truth data in the system is not visible anywhere. (P1)
- **No reporting framework.** Four fixed audit CSVs + one single-day transportation report + a manual-only 4-metric insights recompute. No daily-exceptions, no weekly workload/response/completion by department, no monthly rollups, no date-range/filter/drill-down. (P1)

Transportation is the one department that is genuinely built out (resource engine, calendar, daily report, assignment). It is the reference implementation to generalize from.

---

## 2. Current Admin architecture map

```
Frontend (React CRA/CRACO, react-router)
  /                Landing
  /login /admin-login
  /staff           StaffDashboard      role: staff/admin/owner   (live alert board)
  /front-desk      FrontDeskDashboard  role: front_desk/admin/owner
  /admin           Admin.jsx           role: admin/owner         (25+ tabs, 5 groups)
  /admin/blueprint ownerOnly
  /aria            AriaVoice           ownerOnly
  /kiosk/:id  /family/:token           public

Admin.jsx tab groups (frontend/src/lib/adminTabGroups.js)
  Residents & care         residents · clinician · family · meds
  Communication & requests requests · tasks · schedule · menu ·
                           transportation · transport-calendar ·
                           transport-resources · departments
  Facility & staff         staff · zones · map · (facilities: owner)
  Devices & hardware       rf(pendants) · wearables · devices · kiosks · tokens · hardware
  Reports                  insights · audit · escalation · roadmap
  (global overlays)        AdminAria assistant · AriaSpotlight

Backend (FastAPI, one APIRouter prefix /api, Motor/MongoDB)
  server.py registers ~55 route modules. Auth: JWT (bcrypt) + legacy Google
  session exchange. Roles: owner | admin | staff | front_desk.
  Startup: optional demo seed (off by default) + always-seed default departments.
  No background scheduler / cron / APScheduler anywhere.

Shared operational spine
  StaffTask   (backend/models.py)  — daily chores + resident-request bus +
              transportation requests + department work, all one collection
  Receipt     — generic "something meaningful happened", points at a domain object
  CaosEvent   — append-only telemetry/trace log
  Department  — admin-managed routing targets (slug + label)
  Alert       — safety events AND (since 2026-09-06) the Level 1 resident-
              assistance "ResidentEvent" (presses[], aria_state, live_line_state,
              event_log[], pattern_footnote, ...)
```

Data-flow pattern that works well and should be preserved: **resident/Aria/kiosk → `POST /tasks/resident-request` (or `/transportation/request`) → one `StaffTask` + `Receipt` + department email → same records read by RequestsBoard, DepartmentWorkspaceDialog, RequestDetailDialog, Aria's `check_request_status`, and the audit CSV.** One source of truth, already realised for requests.

---

## 3. Page / screen inventory

| Screen | File | Reads | Writes | State |
|---|---|---|---|---|
| Landing / logins | `Landing.jsx`, `Login.jsx`, `AdminLogin.jsx` | `/auth/*` | session | WORKING |
| Staff live board | `StaffDashboard.jsx` | `/alerts/feed`, `/alerts/stats`, `/locations/latest`, `/insights/summary` | ack/resolve/live-line-answer | WORKING (alert-only) |
| Front desk home | `FrontDeskDashboard.jsx` | reuses TransportationCalendar + RequestsBoard + `/residents` | via children | WORKING |
| Admin shell | `Admin.jsx` | `/residents /staff /kiosks /zones /facilities` | — | WORKING; **opens on Residents, no overview** |
| Residents | `ResidentsTab.jsx` + dialogs | `/residents`, analytics, memory | full CRUD | WORKING |
| Clinician | `ClinicianTab.jsx` | `/residents/{id}/stats` | — | PARTIAL (AI-summary card reads a field `/stats` never returns) |
| Family | `FamilyTab.jsx` | `/family-contacts` | CRUD | WORKING |
| Meds | `MedicationsTab.jsx` | `/medications*` | CRUD + acks | WORKING |
| Requests | `RequestsBoard.jsx` + `RequestDetailDialog.jsx` | `/tasks` (source != staff), `/tasks/{id}/detail` | acknowledge/start/complete, resident-visible schedule+note | WORKING; **no assign / no priority change** |
| Tasks | `TasksTab.jsx` | `/tasks`, `/tasks/templates/all` | CRUD, spawn-today, start/complete/skip | WORKING |
| Schedule (activities) | `ScheduleTab.jsx` | `/schedule` | CRUD | WORKING (Aria read lane) |
| Menu | `MenuTab.jsx` | `/menu`, `/menu/uploads` | CRUD, approve, dev-test ingest | WORKING (read lane + approval gate); **no meal choice/refusal/counts** |
| Transportation ops | `TransportationTab.jsx` | `/transportation/report` (single day) | seed slots, assign | WORKING |
| Transport calendar | `TransportationCalendar.jsx` | `/transportation/calendar` | assign | WORKING |
| Transport resources | `TransportResourcesTab.jsx` | drivers/vehicles/scheduling-config | CRUD | WORKING |
| Departments | `DepartmentsTab.jsx` + `DepartmentWorkspaceDialog.jsx` | `/departments`, `/tasks?visibility_role=` | dept CRUD only | PARTIAL (workspace is **read-only**, admin-only) |
| Staff | `StaffTab.jsx` | `/staff` | create (name/email/pw/role), delete, set-password | WORKING; **no department field** |
| Zones | `ZonesTab.jsx` | `/zones` | CRUD | WORKING |
| Map | `FloorPlanTab.jsx` | zones/residents/locations | — | WORKING (simulated locations) |
| Facilities | `FacilitiesTab.jsx` | `/facilities` | CRUD (owner) | WORKING |
| Pendants (RF) | `RFPairingTab.jsx` | `/rf/*`, `/rf/bridges/active` | pair/assign/test | WORKING (other lane) |
| Wearables | `WearablesTab.jsx` | `/wearables` | CRUD | WORKING |
| Smart devices | `DevicesTab.jsx` | `/devices` | CRUD + command | WORKING for `mock`; real protocols pending hardware |
| Kiosks | `KiosksTab.jsx` | `/kiosks` | CRUD | WORKING |
| Device tokens | `DeviceTokensTab.jsx` | `/device-auth` | CRUD | WORKING |
| Hardware | `HardwareReceiptsTab.jsx` | `/hardware/*` | probe/receipt/assign-role | WORKING (onboarding pipeline, not live health) |
| Insights | `Insights.jsx` | `/insights` | `/insights/compute` (manual) | PARTIAL |
| Audit | `AuditTab.jsx` | `/audit/summary` + 4 CSVs | export | WORKING (fixed set) |
| Escalation | `EscalationTab.jsx` | `/escalation/rule` | save rule, manual tick | PARTIAL (no automation) |
| Roadmap | `Roadmap.jsx` | `/roadmap` | status/notes | WORKING (build tracking, not ops) |
| Device status (on `/staff`) | `DeviceStatusCard.jsx` | `/pendants` (retired), `/wearables`, `/kiosks`, `/alerts` | — | PARTIAL (broken pendant source; wrong wearable battery field) |
| Alert detail | `AlertDetailDialog.jsx` | `/alerts/{id}` | close w/ outcome | PARTIAL (timeline omits Level 1 `event_log[]`) |

**No screen exists for:** operations overview / attention queue, maintenance work orders, housekeeping rooms, resident-assistance event lifecycle table, operational receipts browser, events/telemetry explorer, notification log, system/device health, weekly/monthly reports, shift handoff, fire-drill mode.

---

## 4. Backend / API inventory (operational surface)

Registered and relevant to this audit (full list: `backend/server.py`):

**Tasks / requests spine**
- `GET/POST /tasks`, `PATCH /tasks/{id}`, `POST /tasks/{id}/{acknowledge|start|complete|skip}`, `DELETE /tasks/{id}`
- `GET /tasks/templates/all`, `POST /tasks/templates`, `DELETE /tasks/templates/{id}`, `POST /tasks/spawn-today`
- `GET /tasks/{id}/detail` (task + its receipts)
- `POST /tasks/resident-request`, `GET /tasks/resident-request/{status,mine}` (public, no-auth resident lane)
- List filters: `mine_only`, `status`, `day`, `category`, `visibility_role`, `resident_id`. Staff role is department-scoped **iff `user.department` is set** (it never is — see §10).

**Departments**
- `GET/POST /departments`, `PATCH/DELETE /departments/{id}`; `seed_default_departments()` at startup → `Nursing, Maintenance, Kitchen, Housekeeping, Administration, Transportation`.
- `get_active_departments()` / `get_request_categories()` feed Aria's tool enum at session-mint.

**Alerts / resident-assistance events** (other lane owns the write path)
- `POST /alerts` (public, coalesced), `GET /alerts`, `GET /alerts/feed` (inline lazy escalation 60/180/420 s), `GET /alerts/stats`, `POST /alerts/{id}/{acknowledge,resolve,close}`, `GET /alerts/{id}` (server-built timeline), `GET /alerts/public/{id}/status`
- `POST /alerts/{id}/aria-event`, `/live-line/{ring,answer,no-answer}` (Level 1 lifecycle)

**Escalation**
- `GET/PUT /escalation/rule` (facility-scoped, defaults on miss), `POST /escalation/tick` (manual), `POST /escalation/memory/sanitize` (owner)

**Transportation** (well-developed)
- `POST /transportation/request|/request/{id}/change|/cancel|/complete`, `GET /transportation/availability/public`
- `GET /transportation/report` (single day), `GET /transportation/calendar` (day/week)
- `GET/POST/PATCH/DELETE /transportation/{drivers,vehicles}`, `GET/PUT /transportation/scheduling-config`
- `POST /transportation/request/{id}/assign` (+ `/assign/context`), legacy slot seed
- Engine: `backend/transportation_engine.py`, models: `backend/models_transportation.py`

**Reporting / observability**
- `GET /audit/{alerts,tasks,pages,medications}.csv` + `/audit/summary` (date-ranged, admin)
- `GET /insights`, `GET /insights/summary`, `GET /insights/resident/{id}`, `POST /insights/compute` (manual, wipes+recreates)
- `GET /residents/{id}/{stats,movement,briefing}` (clinical aggregates)
- `GET /receipts`, `GET /receipts/{id}` (admin) — **no UI**
- `GET /events`, `GET /events/conversation/{id}` (admin) — **no UI**
- `GET /notifications`, `GET /notifications/status`, `POST /notifications/test` — **no list UI**

**Devices / hardware / health**
- `GET/POST/PATCH/DELETE /devices` + `/devices/{id}/command`, `/devices/queue/{room}`, `/devices/queue/{cmd}/ack`
- `GET/POST /hardware/{devices,probe,assign-role}`, `/hardware/{profiles,roles}`, `/hardware/devices/{id}/receipt`
- `GET /rf/bridges/active` (bridge daemon liveness — consumed only by RF pairing UI)
- `GET /paging/feed`, `POST /paging/event`
- Pendant/wearable `last_seen_at` + `status`; kiosk `status` field exists but **nothing sets it to `offline`**.

**Helpers called in-process (not HTTP):** `create_receipt()` / `update_receipt_status()` (callers: tasks, transportation, resident_requests, alerts, residents, devices, admin_assistant, resident_activation), `log_event()` (callers: admin_assistant, realtime_diagnostics, devices — **not** tasks/alerts/transportation), `notify_department()` (tasks, resident_requests, transportation).

---

## 5. Database / data inventory

Collections in use (from `db.<name>` references):

```
Operational:   staff_tasks · task_templates · receipts · events · departments ·
               transport_drivers · transport_vehicles · transport_runs ·
               transport_slots · transport_scheduling_config · schedule_items ·
               menu_items · menu_uploads · notifications · pager_events
Safety/events: alerts · resident_button_patterns · resident_assistance_config ·
               escalation_rules · med_reminders · med_ack
Residents:     residents · memories · family_contacts · insights · locations
Devices:       smart_devices · device_commands · pendants (RETIRED) · rf_devices ·
               rf_captures · rf_events · pendant_unknown · wearables ·
               hardware_devices · hardware_receipts · device_tokens · kiosks · zones
Voice/Aria:    conversations · chat_messages · aria_* · realtime_diagnostics ·
               resident_aria_leases
Identity:      users · user_sessions · facilities
```

**Data that already exists and dashboards do not use:**

| Data | Where it lives | Not surfaced in |
|---|---|---|
| Every task/request/device/alert lifecycle event with real timestamps | `db.receipts` | any admin screen (only inside one task dialog) |
| Full telemetry trace (Aria messages, tool calls, device commands, UI actions) | `db.events` | any admin screen |
| Level 1 event lifecycle: `presses[]`, `aria_state`, `live_line_state`, `event_log[]`, `pattern_footnote`, `requested_staff`, `silence_after_invite`, `response_seconds`, `duration_seconds`, `conversation_turns` | `db.alerts` | `AlertDetailDialog` timeline (partially on `StaffDashboard` card only); no aggregate/report anywhere |
| Per-resident hour-of-day button patterns | `db.resident_button_patterns` | any admin screen (used only as an inline footnote at event-open) |
| Notification send/log history | `db.notifications` | any admin screen |
| RF bridge-daemon liveness per kiosk | `db.kiosks.last_bridge_poll_at` | only the RF pairing dropdown |
| Transport run driver/vehicle/return-time/notes | `db.transport_runs` | calendar shows driver/vehicle name only; no history/utilisation report |
| `re_request_count` / `last_re_requested_at` (how many times a resident chased a request) | `db.staff_tasks` | RequestsBoard shows a badge; no "most-chased open items" report |
| `zone.is_restricted` wander config → geofence alert path | `db.zones` / `location.py` | works, but only fires from simulated location pings |

---

## 6. WORKING items (traced UI → API → DB)

- **Auth & roles** — JWT login, session, `require_admin`/`require_owner`, front-desk tier, owner-only routes. Legacy Google exchange present.
- **Residents** — CRUD, preferred-name, clinical thresholds, memory bins, `/movement`, `/stats`, `/briefing`.
- **Staff accounts** — list / create (name, email, password, role) / delete / admin password reset.
- **Alerts / resident-assistance events** — create (resident-scoped coalescing), feed, stats, acknowledge, resolve, close with outcome+category, `response_seconds`/`duration_seconds` computed, receipt opened at event-open and completed at close, pattern footnote generated once ≥ `pattern_min_events`. Level 1 fields written on every transition.
- **Staff tasks** — templates → `spawn-today` (idempotent), one-off create, start/complete/skip/acknowledge with duration + notes + completed-by, receipts wired at each transition, `mine_only` queue on `/staff`.
- **Communication & Requests** — `RequestsBoard` (filter by status/priority/department/search), `RequestDetailDialog` (acknowledge/start/complete + resident-visible schedule/note that Aria reads back), receipt-derived timeline, re-request dedup with history.
- **Departments** — CRUD, activate/deactivate (soft), slug immutable, three-tier notify fallback (`Department.contact_email` → staff by `department` → admin/owner).
- **Transportation** — request/change/cancel/complete, resource engine (drivers, vehicles, runs, buffer policy, atomic capacity guard, shared runs), availability check, daily reconciled report, day/week calendar, pending-ride assignment, resources config tab. Booking truth = `transport_run_id` set + receipt, never "status".
- **Schedule (activities)** — CRUD; Aria speaks only from listed items.
- **Menu** — CRUD with `draft → approved` gate (Aria never reads a draft), superseded-batch history, dev-test email ingestion pipeline (`parse → draft → approve`).
- **Medications** — reminders CRUD, per-day acks, `by-room` due lists, audit CSV.
- **Insights** — 4 per-resident metrics (help requests, nighttime activity, zone mobility, bathroom frequency), 7-day vs prior-7-day, severity + confidence, `/summary` badge on `/staff`.
- **Audit exports** — `alerts.csv`, `tasks.csv`, `pages.csv`, `medications.csv`, date-ranged, admin-only, `/audit/summary` counts.
- **Escalation rule** — facility-scoped config CRUD; `GET` returns defaults on miss.
- **Hardware pipeline** — device registry → capability probe → signed 90-day receipt → role assignment gated on a passing non-expired receipt.
- **Smart devices** — CRUD, command queue, `mock` protocol executes end-to-end; bridge queue path for real protocols.
- **RF pendants** — pairing, bridge-liveness-aware kiosk dropdown, assign/test (other lane).
- **Kiosks / Zones / Map / Family contacts / Device tokens / Wearables** — CRUD.
- **Front Desk dashboard** — transport calendar + requests board + resident directory, reusing the same components/endpoints as Admin.
- **Receipts & Events collections** — genuinely populated by their in-process helpers (verified callers exist).

---

## 7. PARTIAL items

| Item | What works | What's missing / broken |
|---|---|---|
| **Auto-escalation** | Rule config; manual "Run tick now"; `GET /alerts/feed` bumps `escalation_level` inline while a dashboard polls | No scheduler → supervisor/on-call notification path never fires on its own. Two implementations disagree: `alerts.py` feed uses 60/180/420 s and levels 0-3; `escalation.py` tick uses rule `level_2_seconds`/`level_3_seconds` (90/150) and queries statuses `["open","active","acknowledged","escalated"]` + writes `status="escalated"` — neither `"open"` nor `"escalated"` is in the `Alert.status` literal (`active`/`acknowledged`/`resolved`). |
| **Resident-assistance event visibility** | `StaffDashboard` card shows `press_count`, press timestamps, `pattern_footnote`, `aria_state`, `silence_after_invite`, live-line ringing + Answer | `AlertDetailDialog` timeline (built in `alerts.py::get_alert`) omits `event_log[]`, `presses[]`, `aria_state`, live-line states, `requested_staff`. No admin/clinician **aggregate**: minutes-open distribution, press-count distribution, silence/no-response rate, live-line answer/decline/no-answer rate, resolution mix. |
| **Clinician tab** | KPIs, category breakdown, recent events from `/residents/{id}/stats` | "AI summary" card renders `stats.narrative`; `/stats` never returns `narrative` (only `/briefing` does) → card is always the placeholder text. |
| **Device status card** (`/staff`) | Wearable + kiosk counts; recent device-triggered alerts | Reads `/pendants` (the collection `adminTabGroups.js` documents as **retired**, replaced by `rf_devices`) → pendant panel is empty in reality. Uses `w.battery_pct`; model field is `battery_percent` → wearable battery never renders. |
| **Insights** | 4 metrics, manual recompute | No scheduler; each run `delete_many({})` then recompute → no history/trend of the insights themselves. Alert-count based only (no request/task/response-time signal). Not wired to any per-department view. |
| **Transportation report** | Single reconciled day: inbound / outbound / current state / summary / slot utilisation | No CSV export, no multi-day range, no weekly/monthly rollup, no per-driver / per-vehicle utilisation history, no on-time vs late, no return-trip tracking. |
| **Department workspace** | Opens per department, lists open/completed/skipped tasks by `visibility_role` slug, age label | Read-only — no assign, no status change, no priority. `DepartmentsTab` is admin-only, so the department's own staff cannot reach their queue this way. |
| **Menu** | Read lane + approval gate + dev-test ingestion | No meal-choice collection, refusal, switchover, per-resident selection, kitchen counts, dietary flags (all in the operations contract). |
| **Map / locations** | Renders latest zone per resident | Location source is `mock`; "Simulate" button generates pings. No real mesh. Wander/geofence alert path is real but only triggered by simulated pings. |

---

## 8. MOCK / TEST-ONLY items

- **Smart-device protocols** — only `mock` executes end-to-end. Per `PROJECT_STATE.md`: one real Matter bulb working, one Midea AC blocked at the Matter CASE layer. `home_assistant/bluetooth/wifi/rf_*/ir/zigbee/matter` are wired for the bridge-queue path but pending hardware in most rooms.
- **Menu email ingestion** — `POST /menu/ingest/dev-test` with a pasted "email body"; no mailbox connected. Explicitly a pipeline-proving stub.
- **Notifications** — Twilio + Resend unconfigured → `send_sms`/`send_email` record `status="logged"` and return. Live-line Twilio **voice** call is a logging no-op (`twilio` package not installed). Escalation SMS likewise.
- **Locations** — `LocationUpdateCreate.source` includes `"mock"`; `POST /locations/mock/generate` + the "Simulate" button on `/staff` are the only producers in this deployment.
- **Seed scripts** (`backend/scripts/`) — `seed_department_engagement.py`, `seed_transportation_pilot.py`, `seed_menu_two_weeks.py`, `seed_schedule_two_weeks.py`, `seed_mock_devices.py`, `seed_mock_residents.py`, `seed_demo_announcements.py`. Demo-data generators; `CAOSCARE_ENABLE_DEMO_SEED` defaults false.
- **`test_result.md` / `test_reports/`** — historical automated-test artefacts, not runtime.

---

## 9. DISCONNECTED items (built, but nothing consumes them)

- **`GET /receipts`, `GET /receipts/{id}`** — admin-gated, no admin screen. The generic operational receipt is only ever seen inside `RequestDetailDialog` via `/tasks/{id}/detail`.
- **`GET /events`, `GET /events/conversation/{id}`** — admin-gated, no admin screen. `ConversationSessionDetail` reconstructs from `conversations`/`realtime_diagnostics`, not `/events`.
- **`GET /notifications`** — no list UI. (`CAOSCARE_OPERATIONS_GAP_MAP.md` lists "notification log" as an existing surface; it is an endpoint only.)
- **`User.department`** — no create/edit path anywhere (`RegisterInput` has no field, `StaffTab` has no control, `staff.py` has no `PATCH`). Consequences: department-scoped `list_tasks` never activates for staff; `notify_department` step 2 always empty → admin/owner fallback; `DepartmentWorkspaceDialog` shows work no department member can be routed to.
- **`Alert.event_log[]` / Level 1 lifecycle** — written on every Aria/live-line transition; not rendered in the detail view.
- **`db.resident_button_patterns`** — computed and stored on every event close; only ever read as a one-line footnote at the next event-open. No pattern browser.
- **`POST /escalation/tick`** — no automatic caller.
- **`POST /insights/compute`** — no automatic caller.
- **`/hardware` receipts & role assignment** — a working onboarding pipeline, but no screen surfaces "which fielded devices have an expired/failing receipt" as an operational health signal.
- **`GET /rf/bridges/active`** — consumed only by the RF pairing dropdown; not part of any health view.
- **`kiosks.status`** — field exists; no code path sets `offline`; no heartbeat.

---

## 10. MISSING items (in the operations contract / directive, not built)

**Executive / Admin dashboard** — none. No attention queue, no "what changed", no overdue view, no ownership rollup, no time-open, no trend, no offline/broken panel, no follow-up list. `/admin` opens on Residents.

**Maintenance** — no `WorkOrder` model. Missing: work-order source (resident/staff/system), category taxonomy, priority + safety-impact + resident-impact classification, assignee workflow, **age of work order**, first/last activity timestamps, **overdue** state, **repeat-issue** detection, previous-related-work linkage, vendor / outside-service tracking, parts/materials, cost, distinct close reason, `blocked`/`waiting_parts`/`waiting_vendor` statuses, preventive-maintenance rounds/checklists, room-readiness / move-in-move-out workflow, life-safety equipment checks. Today: a `StaffTask` with `category="maintenance"`.

**Housekeeping** — no model. Missing: room-by-room assignment board, per-room status, daily/weekly/deep-clean templates keyed to rooms, room-turn workflow, inspections, workload-by-staff view, coverage/staffing view, late/missed tracking, unable-to-complete reason, handoff-to-maintenance routing.

**Transportation** (on top of the strong base) — recurring rides, late/missed/no-show tracking, return-trip confirmation, per-resident ride history view, driver/vehicle utilisation reporting, weekly/monthly report, CSV export, appointment vs pickup-time distinction beyond a free-text label.

**Resident-assistance operations view** — no staff/Admin table of open events with: resident, room, open time, **minutes open**, **press count**, Aria state, **silence / no-response** flag, staff response time, resolution, outcome, receipt link. Data exists on `Alert`; no view assembles it. (Leave a documented seam for the personal-baseline/deviation feed the other workstream will add.)

**Room / device / system health** — no consolidated view of: room node, kiosk, microphone, speaker, RF listener, pendant mapping, smart devices, Home Assistant state, connectivity, last successful command, failures, stale/offline devices, UPS/power. Signals are scattered across `DeviceStatusCard` (broken source), `/rf/bridges/active`, `/hardware`, `last_seen_at`, and an unset `kiosks.status`.

**Reporting** —
- *Daily:* no exceptions report, no overdue-work report, no open-assistance-events report, no maintenance-aging report, no transportation-problems report, no housekeeping-misses report, no device-failure report.
- *Weekly:* no workload-by-department, no response-time, no completion-time, no repeat-problems, no open-vs-closed, no operational-trend report.
- *Monthly:* no department performance, volume, aging, recurring-issue, or asset-trend report.
- No shared reporting framework (date ranges, filters, drill-down, export). Present: 4 fixed audit CSVs + 1 single-day transportation report + manual insights.

**Role-based dashboards** — only staff (alert board), front-desk, and admin. No maintenance / housekeeping / transportation / care role home. `roleHomePath()` sends every non-`front_desk`, non-`admin`/`owner` user to `/staff`.

**SLA / overdue** — `StaffTask.due_at` is set only on manual one-off creation; templates never set it; nothing computes or badges "overdue". `requested_for_date` is a resident-visible ETA, not an SLA.

**Cross-department follow-up routing** — no housekeeping→maintenance (or any→any) handoff object.

**Shift handoff** — no `ShiftHandoff` model or summary generator.

**Fire drill / room-check mode** — not built (operations contract Phase 3).

---

## 11. Maintenance workflow gaps

| Contract requirement | Status |
|---|---|
| Work-order intake with source (resident/staff/system) | Generic `StaffTask` only; `source` enum exists but no maintenance intake form |
| Room/location, category, priority | `room` + `category` string; **no priority classification, no safety/resident-impact flags** |
| Assignee, created time | `assigned_to` (set to whoever clicks Start), `created_at` |
| **Age of work order** | Not computed anywhere |
| Last activity, overdue state | Not tracked |
| Repeat issue / previous related work | Not tracked / not linked |
| Vendor / outside service | Not modelled |
| Parts / materials, cost | Not modelled |
| Statuses: new/triaged/assigned/in_progress/blocked/waiting_parts/waiting_vendor/completed/verified/cancelled | `StaffTask` has only `pending/in_progress/completed/skipped`; **no blocked/waiting/verified** |
| Close reason (distinct from notes) | Only free-text `notes` |
| Verified-by | Not modelled (no second-signoff) |
| Preventive-maintenance rounds / recurring inspections | `StaffTaskTemplate` can recur but has no checklist-run, no per-item checkoff, no PM cadence semantics |
| Room readiness / move-in-move-out | Not built |
| Receipts / history / reports | Generic receipts fire on task transitions; no maintenance-specific report |

**Verdict:** Maintenance is unmodelled. This is the single largest build gap and the stated top priority.

---

## 12. Housekeeping workflow gaps

| Contract requirement | Status |
|---|---|
| Assigned rooms / tasks | Only via generic `StaffTask` with `category="housekeeping"` (a category option in `TasksTab`) |
| Schedules, recurring tasks | Generic `StaffTaskTemplate` (no room-keyed recurrence, no per-room schedule) |
| Status by room | Not modelled (task-centric, not room-centric) |
| Completion, late/missed work | `completed_at` per task; **no missed/late detection**, no expected-by |
| Room turns, deep cleans, inspections | Not modelled |
| Workload by staff, staffing coverage | Not built |
| Handoff to maintenance when an issue is found | Not built |
| History / reporting | Generic receipts only; no housekeeping report |

**Verdict:** No housekeeping module. `housekeeping` is a task-category label and a department slug.

---

## 13. Transportation workflow gaps

Transportation is the **most complete** operational department. Gaps are refinements, not foundations.

| Requirement | Status |
|---|---|
| Resident, destination, purpose, date, time label | WORKING (`StaffTask` category=transportation + `TransportRequestInput`) |
| Pickup / depart time, return time | `TransportRun.depart_time` WORKING; `return_time` optional and rarely set; **no return-trip confirmation** |
| Driver, vehicle | `TransportRun.driver_id`/`vehicle_id` **optional** — a `status="confirmed"` run can have neither |
| Status | `RunStatus` (confirmed/in_progress/completed/cancelled) WORKING |
| Assignment | `POST /transportation/request/{id}/assign` + `TransportAssignAction` WORKING |
| Recurring rides | Not built |
| Late / missed / no-show | Not tracked |
| Notes | `TransportRun.notes` exists; minimal surfacing |
| History (per resident) | No per-resident ride history view |
| Daily schedule | WORKING (calendar day/week + daily report) |
| Reporting | Single-day reconciled report only; **no weekly/monthly, no CSV, no driver/vehicle utilisation history, no on-time metric** |

---

## 14. Reporting gaps

**What exists:** `audit/{alerts,tasks,pages,medications}.csv` (date-ranged, admin), `transportation/report` (one day), `insights` (manual, 4 metrics, no history), per-resident `stats`/`briefing`.

**Missing — daily:** exceptions digest, overdue work, open assistance events (with minutes-open), maintenance aging, transportation problems (late/unbooked/chased), housekeeping misses, device/system failures.

**Missing — weekly:** workload by department, response times (alert + request), completion times, repeat problems, open vs closed, operational trend lines.

**Missing — monthly:** department performance, volume, aging distribution, recurring issues, asset/problem trends.

**Missing — framework:** a single report surface with date-range picker, department/category/status/room filters, drill-down to the underlying records, and export. The building blocks (`receipts`, `events`, `staff_tasks`, `alerts`) are all queryable and timestamped; nothing assembles them.

**Constraint to honour:** reports must distinguish fact from inference and must not fabricate analytics to fill charts (per `CAOSCARE_FACILITY_OPERATIONS_CONTRACT.md` §"Reporting requirements"). Several needed reports will legitimately be empty until maintenance/housekeeping data exists.

---

## 15. Role / permission gaps

- **`staff` role is monolithic.** No sub-role or department. `roleHomePath()` → everyone lands on the alert board (`/staff`). Maintenance/housekeeping/transportation/care staff all see the same screen.
- **`User.department` cannot be set** (§9). This disables department-scoped task visibility, department notification targeting, and any future department dashboard gating.
- **`RequestsBoard` / `RequestDetailDialog`** are inside `/admin` (adminOnly). Line staff cannot triage or update requests routed to their department except via the generic `/staff` "My tasks" card, and only if a task is already `assigned_to` them.
- **`DepartmentWorkspaceDialog`** is reachable only from `DepartmentsTab` (adminOnly) and is read-only.
- **Front Desk** has a purpose-built home; that is the pattern the other operational roles need.
- **Clinical vs non-clinical data separation** is nominal: `visibility_role` on tasks is enforced in `list_tasks` for `role=="staff"` **only when `user.department` is set**. With it unset, the guard clause resolves to `all_staff` and no separation occurs.
- Positive: `require_admin`/`require_owner`/`frontDeskOnly` route gating is consistent and correct where applied.

---

## 16. Navigation / UX problems

- **No landing overview.** `/admin` opens on "Residents (N)". First thing an administrator sees is a resident list, not "what needs me today."
- **"Reports" group contains no reports.** Insights (4 metrics), Audit (CSV export), Escalation (a *config* screen), Roadmap (build tracking).
- **Transportation occupies 3 of 8 tabs** in "Communication & requests" (Transportation, Transport calendar, Transport resources) while Maintenance/Housekeeping have zero.
- **25+ tabs across 5 groups**, flat within each group, no counts-of-what-matters, no cross-tab search or date scope.
- **Departments** is buried under "Communication & requests"; its workspace is a dead-end (read-only).
- **`DeviceStatusCard`** on `/staff` shows a permanently empty pendant panel (retired endpoint) — actively misleading about device health.
- **Escalation tab** presents a manual "Run tick now" button as if escalation is otherwise automatic; it is not.
- The **AdminAria assistant** can navigate tabs and take some actions, partially compensating for the flat nav — but it is an overlay, not structure.

---

## 17. Data-model gaps

- **No dedicated models:** `MaintenanceWorkOrder`, `MaintenanceChecklist{Template,Run,Item}`, `HousekeepingRoomTask`, `HousekeepingChecklist*`, `PreventiveMaintenanceRound`, `RoomReadinessChecklist`, `DrillEvent`/`RoomCheck`, `MealChoice`/`MealRefusal`/`MealSwitchover`, `ShiftHandoff`/`HandoffItem`, `FollowUpRoute` (all enumerated in `CAOSCARE_OPERATIONS_GAP_MAP.md`).
- **`StaffTask` is overloaded** across four roles (daily chores, resident-request bus, transportation request, department work) with no discriminator beyond `source`/`category`, and lacks: `age`/`first_activity_at`/`last_activity_at`, `sla_due_at`, `overdue`, `reopened`/`reopened_at`, `related_task_ids`, `close_reason` (distinct from `notes`), `assigned_at`/assignment history, and any maintenance fields (`vendor`, `parts`, `cost`, `safety_impact`, `resident_impact`).
- **`User.department` is single-valued and unpopulated** — a staff member cannot belong to two departments; nothing sets it at all.
- **`Alert` is doubling as `ResidentEvent`.** `Alert.status` literal lacks `"escalated"` even though `escalation.py` writes it; `"open"` is queried but never written. `activation_consumed_at` vs `status` vs `aria_state` vs `live_line_state` is a lot of lifecycle state on one document with no single derived "event phase".
- **`facility_id`** is `Optional` on most models and not enforced in queries — multi-tenant is structural intent, not runtime reality.
- **`TransportRun.driver_id`/`vehicle_id` optional** on a `confirmed` run.
- **`Receipt` and `CaosEvent` are never rolled up.** Every prospective report must full-scan; there is no materialised metric, no daily aggregate, no index strategy documented.
- **`due_at` on `StaffTask`** is a `datetime`; `requested_for_date`/`requested_for_time_label` are strings; two different "when" representations coexist.

---

## 18. Highest-value fixes (ranked)

### P0 — blocks real operation

1. **Staff ↔ department assignment.** Add `department` to staff create + an editable control (`StaffTab` + a `PATCH /staff/{id}` or a `StaffUpdate`), and expose active departments as the option list. This one change activates department-scoped task visibility, correct department notification, and any department dashboard. *Nothing else in the role/department story works until this exists.*
2. **Maintenance work-order module.** New model + routes + tab: source, category, priority, safety/resident impact, assignee, status set incl. `blocked`/`waiting_parts`/`waiting_vendor`/`verified`, **age**, first/last activity, **overdue**, close reason, vendor, parts, optional cost, activity log via existing `Receipt`/`Event` helpers. Build it as the generalisable template (housekeeping reuses the shape).
3. **Operations overview dashboard** (new page, read-only over existing data). Attention queue: overdue tasks, unacknowledged alerts/requests, re-requested items (`re_request_count > 0`), escalated alerts, unbooked transportation, open resident-assistance events with minutes-open. KPI strip: open by department, aging buckets, completed today, exceptions today. Offline/stale devices panel. No new writes — pure aggregation of `staff_tasks` + `alerts` + `receipts` + `transport_runs`.

### P1 — important operational capability

4. **Automate escalation** — a scheduled tick (deploy cron calling `POST /escalation/tick`, documented in the runbook, or an in-process interval task) **and** reconcile the two escalation implementations into one (thresholds, statuses, the `"escalated"`/`"open"` literal mismatch). *Coordinate — touches `alerts.py` which the other lane owns.*
5. **Operational receipts + events browser** — an admin screen over `GET /receipts` and `GET /events` with filters (object type, resident, room, actor, date range) and drill-down. Turns the system's best existing data into visibility.
6. **Reporting framework** — one report surface: date range + department/category/status filters + CSV. First reports: daily exceptions, weekly workload/response/completion by department, open-vs-closed. Derived from `receipts` + `staff_tasks` + `alerts`.
7. **Housekeeping room-status workflow** — room list with per-room status, room-keyed recurring templates, missed/late detection, unable-to-complete reason, handoff-to-maintenance (shared `FollowUpRoute` with fix #2).
8. **Make the department workspace actionable** — assign, status, priority from `DepartmentWorkspaceDialog`; and give the owning department's staff a route to their own queue (a role home or a `/staff` department view).
9. **Resident-assistance operations view** — a table over existing `Alert` fields: open time, minutes open, press count, `aria_state`, `silence_after_invite`, response time, live-line outcome, resolution, receipt link. Add a `// integration point:` seam for the personal-baseline/deviation feed. *Read-only; do not touch the write path.*
10. **Fix `DeviceStatusCard`** — point pendant status at `rf_devices` (or replace the card), fix `battery_pct` → `battery_percent`. Small, high-signal correctness fix. *Note: this card renders on `StaffDashboard`, which the other lane edits — keep the diff surgical.*

### P2 — useful enhancement

11. **SLA / overdue** on tasks + templates (per-category default `sla_hours`, computed `overdue`, badges, feeds the overview).
12. **Repeat-issue detection** — link related tasks by room + category (+ keyword) and surface "recurring problems".
13. **Transportation** — recurring rides, late/missed, per-resident history, weekly/monthly report + CSV, driver/vehicle utilisation.
14. **Role-specific home routes** for maintenance / housekeeping / transportation / care (mirror `FrontDeskDashboard`).
15. **Central system-health page** — nodes, kiosks (with a real heartbeat setting `kiosks.status`), mics, speakers, RF bridges (`/rf/bridges/active`), HA state, last successful command, stale/offline, hardware-receipt expiry.
16. **Navigation restructure** — dedicated "Operations" group + an "Overview" landing (see §19).

### P3 — later polish

17. Wire `ClinicianTab`'s AI-summary to `/residents/{id}/briefing` narrative.
18. Notification-log UI over `GET /notifications`.
19. Fire-drill / room-check mode (operations contract Phase 3).
20. Meal choice / refusal / switchover (operations contract Phase 2).
21. Document a CMMS (e.g. TELS) adapter boundary — an interface spec only. **Do not build or claim an integration.**

---

## 19. Proposed Admin / dashboard structure

```
/admin  → Overview (new default)
  ├─ Overview        attention queue · KPI strip · aging buckets · today's
  │                  exceptions · offline/stale devices · trend sparklines
  ├─ Operations      Maintenance (work orders + PM rounds)
  │                  Housekeeping (rooms + schedules + turns)
  │                  Transportation (calendar · resources · daily report)
  │                  Requests (cross-department resident/family/front-desk)
  │                  Departments (workspace: assign · status · priority)
  ├─ Residents & care Residents · Clinician · Resident-assistance events (new) ·
  │                  Family · Meds
  ├─ Facility & staff Staff (+ department) · Zones · Map · Facilities
  ├─ Devices & health Pendants (RF) · Wearables · Smart devices · Kiosks ·
  │                  Device tokens · Hardware · System health (new)
  └─ Reports         Daily exceptions · Weekly ops · Monthly · Audit exports ·
                     Insights
  (global)           Admin Aria assistant · Aria Spotlight

Role homes (roleHome.js)
  owner/admin  → /admin (Overview)
  front_desk   → /front-desk         (exists)
  maintenance  → /ops/maintenance    (new: their work orders + building health)
  housekeeping → /ops/housekeeping   (new: their rooms + schedules)
  transport    → /ops/transportation (new: rides + vehicles)
  care/nursing → /staff              (alert board + assigned operational work)
```

Principle to keep: **one dataset, role-specific views.** Every role screen reads the same `staff_tasks` / `alerts` / `transport_runs` — never a parallel store (transportation and requests already prove this).

---

## 20. Exact files likely to change

**New — backend**
- `backend/models_maintenance.py`, `backend/models_housekeeping.py` (kept out of `models.py`, already 1554 lines)
- `backend/routes/maintenance.py`, `backend/routes/housekeeping.py`
- `backend/routes/ops_overview.py` (attention queue / KPI aggregation)
- `backend/routes/reports.py` (report framework + CSV)
- `backend/routes/system_health.py` (device/node health rollup)
- optional `backend/routes/follow_up_routes.py` (cross-department handoff)

**Modified — backend**
- `backend/server.py` — register new routers
- `backend/routes/staff.py` — `department` on create + a `PATCH /staff/{id}`
- `backend/models.py` — `RegisterInput`/`User` (or a new `StaffUpdate`) for `department`; add `StaffTask` aging/SLA fields **or** extract them if it can't grow — file is over the 300-line cap
- `backend/routes/departments.py` — a `staff-in-department` helper if needed
- `backend/routes/tasks.py` — overdue/SLA computation in `list_tasks`; assignment endpoint for the department workspace
- `backend/routes/escalation.py` **and** `backend/routes/alerts.py` — reconcile + automate escalation ⚠️ *shared with the other lane — coordinate*
- `backend/routes/kiosks.py` — a heartbeat that sets `status` ⚠️ *the other lane touches this file for the active-emergency poll — coordinate or add a separate route module*
- `scripts/` / `docs/DEPLOYMENT_RUNBOOK.md` — a cron entry for the escalation/insights ticks

**New — frontend**
- `frontend/src/pages/OperationsOverview.jsx`
- `frontend/src/pages/MaintenanceTab.jsx`, `HousekeepingTab.jsx`
- `frontend/src/pages/ReportsTab.jsx` (+ daily/weekly/monthly subviews)
- `frontend/src/pages/SystemHealthTab.jsx`
- `frontend/src/pages/ResidentAssistanceEventsTab.jsx` (read-only)
- `frontend/src/pages/ReceiptsExplorer.jsx` (receipts + events)

**Modified — frontend**
- `frontend/src/pages/Admin.jsx` — routes + tab content
- `frontend/src/lib/adminTabGroups.js` — nav restructure
- `frontend/src/lib/roleHome.js` — role homes for maintenance/housekeeping/transport
- `frontend/src/pages/StaffTab.jsx` — department control
- `frontend/src/pages/DepartmentWorkspaceDialog.jsx` — actions
- `frontend/src/pages/DeviceStatusCard.jsx` — fix pendant source + battery field ⚠️ *rendered on `StaffDashboard`*
- `frontend/src/pages/ClinicianTab.jsx` — wire narrative from `/briefing` (P3)

**Do NOT touch (other Claude's lane)**
`backend/routes/alerts.py` write path, `alert_lifecycle_events.py`, `resident_activation.py`, `resident_patterns.py`, `resident_assistance_config.py`, `rf*.py`, `realtime*.py`, `kiosks.py` active-emergency poll, `realtime_room_lease.py`; `frontend/src/pages/StaffDashboard.jsx`, `AlertDetailDialog.jsx`, `Kiosk.jsx`, `RealtimeChatScreen.jsx`, `frontend/src/lib/useRealtimeVoice.js`, `frontend/src/lib/realtime*`.

---

## 21. Potential conflicts with the other Claude workstream

| Area | Shared surface | Mitigation |
|---|---|---|
| **`backend/models.py`** | `Alert` model, `StaffTask` model, both in the one file the other lane also edits for Level 1 fields | Put new operational models in `models_maintenance.py` / `models_housekeeping.py`. Do not add fields to `Alert`. If `StaffTask` must gain fields, do it in a tight, well-labelled block and rebase often. |
| **Escalation** | `alerts.py::alerts_feed` inline escalation vs `escalation.py::tick`; reconciling them edits `alerts.py` | Coordinate before touching `alerts.py`. Prefer moving escalation logic entirely into `escalation.py` + a scheduler, leaving `alerts_feed` read-only. |
| **`StaffDashboard.jsx`** | Other lane actively adds press history / `aria_state` / live-line UI here | Build the Operations Overview as a **new page**, not edits to `StaffDashboard`. Only surgical fix here is `DeviceStatusCard` (a child) — keep it to the two field/endpoint corrections. |
| **`AlertDetailDialog.jsx` + `alerts.py::get_alert` timeline** | If the resident-assistance ops view wants `event_log[]` rendered, that is the other lane's write territory | Build a **separate read-only** "event detail" that consumes existing `Alert` fields via `GET /alerts/{id}` without changing the endpoint or the dialog. |
| **`kiosks.py`** | Other lane owns `active_emergency_for_kiosk`; a health heartbeat would add to this file | Add the heartbeat in a new module (`rf_bridge_health.py` is the precedent) rather than editing `kiosks.py`. |
| **`Receipt` / `CaosEvent` semantics** | Both lanes call `create_receipt()` / `log_event()`; the ops browser will render the other lane's `resident_assistance_event` receipts | Read-only consumer — safe. Don't change the helper signatures. |
| **Departments / `visibility_role`** | Aria's tool enum is built from `get_active_departments()` at session mint | Adding maintenance/housekeeping *workflows* doesn't change the department list (slugs already seeded). Safe. Don't rename slugs. |
| **Git** | Shared stash stack across worktrees | Use WIP commits, never bare `git stash`. Commit only `docs/ADMIN_OPERATIONS_AUDIT.md` for this deliverable. |

---

## Appendix A — evidence notes

- `User.department` unset: `RegisterInput` (`backend/models.py`) has no `department`; `backend/routes/staff.py` exposes only `GET`/`POST`/`DELETE`/`POST {id}/password`; `frontend/src/pages/StaffTab.jsx` form is `{name,email,password,role}`. Consumer `backend/routes/tasks.py::list_tasks` staff branch: `q["visibility_role"] = {"$in":[dept,"all_staff"]} if dept else "all_staff"`.
- No scheduler: no `cron`, `APScheduler`, `BackgroundScheduler`, or systemd timer in `backend/`, `scripts/`, or `docs/DEPLOYMENT_RUNBOOK.md`. `server.py` lifespan does seed + `seed_default_departments()` only.
- Escalation literal mismatch: `Alert.status = Literal["active","acknowledged","resolved"]`; `escalation.py::tick` queries `{"status":{"$in":["open","active","acknowledged","escalated"]}}` and `$set` `{"status":"escalated"}`.
- Receipts/events unused by UI: `grep` for `/receipts`, `"/events"`, `NotificationsTab`, `ReceiptsTab` across `frontend/src` → only `HardwareReceiptsTab` (a different `/hardware` surface) and doc-comments.
- `DeviceStatusCard` uses `api.get("/pendants")`; `adminTabGroups.js` documents `pendants`/`PendantsTab` as retired 2026-09-01 in favour of `rf_devices`/`rf_events`. Same card reads `w.battery_pct`; `Wearable` model field is `battery_percent`.
- `ClinicianTab` renders `stats.narrative`; `GET /residents/{id}/stats` returns `{resident, window_days, current_window, previous_window, recent_events}` — no `narrative` (that key is only in `/residents/{id}/briefing`).
- Transportation is the built-out reference: `backend/transportation_engine.py`, `backend/models_transportation.py`, `routes/transportation*.py` (7 modules), `frontend` Transportation/TransportationCalendar/TransportResourcesTab + `TransportAssignAction`.
- Maintenance/housekeeping: `grep -rin "maintenance|housekeeping"` in `backend/` → only `DEFAULT_DEPARTMENTS`, Aria tool-prompt strings, and request-bus category lists. No model, no route module, no dedicated collection.
- `PROJECT_STATE.md` (2026-09-06 entries) is the current-state authority; `BUILD_STATUS.md` predates the operations layer and still says "realtime voice remains planned" — treat it as stale for runtime status.
