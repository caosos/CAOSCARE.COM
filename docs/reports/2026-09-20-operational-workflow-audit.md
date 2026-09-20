# CAOSCare Operational Workflow Audit — 2026-09-20

**Scope:** report-only inspection of the operational layer (Live Board, Community command centre, department queues, transportation, devices, reports, clinician) as it exists on `main` @ `e092e36` in this EliteDesk checkout. No code, data, or config was changed. All Mongo access was read-only (`count_documents`/`find`, no writes). Nothing was committed.

**Primary sources:** `docs/ADMIN_OPERATIONS_AUDIT.md` (2026-09-06, `claude/admin-operations` lane — read first, re-verified against current `main` below since several of its P0 findings have since been built), `docs/CAOSCARE_PRODUCT_BASELINE.md`, `docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md`, `docs/PROJECT_STATE.md`, `docs/tsb/TSB-002-*.md`, and direct source inspection (cited inline).

**What changed since the 2026-09-06 audit (verified, not assumed):** `User.department` is now settable (`backend/routes/staff.py::update_staff`, `frontend/src/pages/StaffTab.jsx`); `GET /api/ops/overview` (Operations overview) exists (`backend/routes/ops_overview.py`); a Maintenance work-order workspace exists on the `StaffTask` spine (`frontend/src/pages/MaintenanceWorkspace.jsx`, `backend/routes/task_assignment.py`); a Reports framework exists (`backend/routes/reports.py`, `frontend/src/pages/ReportsTab.jsx`); an Activity Log (receipts + events browser) exists (`frontend/src/pages/ActivityLog.jsx`, `ReceiptsPanel.jsx`, `EventsPanel.jsx`); the Admin nav now matches the group structure the user's audit list names exactly (`frontend/src/lib/adminTabGroups.js`). The 2026-09-06 audit's P0 #1–#3 are therefore **resolved**, not open, as of this checkout. Its P1/P2 findings on maintenance state-model depth, escalation automation, and reporting depth are **still substantially accurate** — re-verified below where load-bearing for this pass's questions.

---

## 1. CURRENT ARCHITECTURE MAP

```
Frontend (React CRA/CRACO)                    Backend (FastAPI, one /api router, Motor/MongoDB)
  /staff        StaffDashboard.jsx      <---   /alerts/feed, /alerts/stats, /locations/latest, /insights/summary
  /admin        Admin.jsx (7 groups)    <---   ~76 route modules (backend/server.py), JWT + legacy Google auth
    Community     OperationsOverview.jsx  <-   GET /ops/overview            (backend/routes/ops_overview.py)
                  AlertsBoard.jsx         <-   GET /alerts                  (backend/routes/alerts.py)
                  MaintenanceWorkspace    <-   GET /tasks?visibility_role=maintenance (backend/routes/tasks.py)
    Residents&care ResidentsTab -> ResidentRecordDialog -> ResidentHubPanels.jsx (7 sub-panels, own API calls)
    Departments&staff DepartmentsTab, StaffTab, ZonesTab, FloorPlanTab
    Communication  RequestsBoard, TasksTab, ScheduleTab, MenuTab, TransportationTab,
                   TransportationCalendar, TransportResourcesTab
    Devices        RFPairingTab, WearablesTab, DevicesTab, KiosksTab, DeviceTokensTab, HardwareReceiptsTab
    Reports        ReportsTab, ActivityLog, Insights, AuditTab, EscalationTab, Roadmap
  /front-desk   FrontDeskDashboard.jsx  <---   reuses TransportationCalendar + RequestsBoard + /residents
  /kiosk/:id    Kiosk.jsx (public)      <---   resident-facing: devices/requests/schedule polling (§4, §17)

Shared operational spine (one collection, many callers — verified, this is real):
  db.staff_tasks   — daily chores + resident-request bus + transportation requests + department work
  db.alerts        — safety events AND (since 2026-09-06) Level-1 "ResidentEvent" (presses[], aria_state,
                     live_line_state, event_log[], escalations[])
  db.receipts      — generic "something happened", points at a domain object (create_receipt/update_receipt_status)
  db.events        — append-only CaosEvent telemetry (log_event) — narrow coverage, see §5
  db.departments   — admin-managed routing targets
  db.transport_runs / db.transport_drivers / db.transport_vehicles — resource-aware transportation engine

Aria's own "what's happening" unification (Layer E, built 2026-09-08, NOT wired to any human UI — see §5, §9):
  backend/routes/aria_operational_state.py::resolve_operational_state(resident_id, room, alert_id)
  — already merges open db.alerts + open db.staff_tasks into one snapshot with a real lifecycle enum
    (open/acknowledged/answered/in_progress/resolved/escalated) for Aria's own prompt context.
```

No scheduler, no background job runner, no WebSocket/SSE/change-stream infrastructure exists anywhere (verified §13, §17).

---

## 2. DATA OBJECT / COLLECTION / API MAP

| Domain | Model | Collection | Primary routes | Notes |
|---|---|---|---|---|
| Generic staff work + resident requests + transportation requests + department work | `StaffTask` (`backend/models.py:763`) | `db.staff_tasks` | `backend/routes/tasks.py`, `resident_requests.py`, `task_assignment.py`, `task_templates.py`, `task_detail.py` | One overloaded model across 4 use-cases, discriminated by `source`/`category`/`visibility_role`, not a type field |
| Safety alerts + Level-1 resident-assistance events | `Alert` (`models.py:283`) | `db.alerts` | `alerts.py`, `alert_lifecycle_events.py` | `Alert` genuinely doubles as `ResidentEvent` — see §5 |
| RF pendant identity + fingerprint matching | `RFDevice`/`RFEvent` | `db.rf_devices`, `db.rf_events` | `rf.py`, `rf_matched_intake.py`, `rf_fleet.py` | Identity (who) vs semantics (what) are cleanly separated — see §7 |
| RF transmission semantics (help vs supervisory) | n/a (pure functions) | n/a | `rf_semantics.py::classify_transmission` | Gates entry into `record_resident_activation()` — see §7, §12 |
| Resident-assistance activation coalescing | n/a | writes `db.alerts` | `resident_activation.py::record_resident_activation()` | Generalizes RF + kiosk-button into ONE open-incident-per-resident rule — different mechanism from the StaffTask dedup in §12 |
| Transportation resource engine | `TransportDriver`/`TransportVehicle`/`TransportRun`/`TransportSchedulingConfig` (`backend/models_transportation.py`) | `db.transport_drivers`, `db.transport_vehicles`, `db.transport_runs`, `db.transport_scheduling_config` | `transportation.py`, `transportation_calendar.py`, `transportation_resources.py`, `transportation_assign.py` | Legacy hourly `TransportSlot` bucket also still exists (`transportation_legacy_slots.py`) — historical data only, superseded 2026-08-22 |
| Menu | `MenuItem`/`MenuUpload` (`models.py:1028`) | `db.menu_items`, `db.menu_uploads` | `menu.py`, `menu_ingest.py`, `email_inbound.py` (new, this session — real Resend inbound, uncommitted... **committed** as `e092e36`) | Draft→approved gate; superseded-batch history on re-approval |
| Activities schedule | `ScheduleItem` (`models.py:951`) | `db.schedule_items` | `schedule.py`, `schedule_ingest.py` | **No draft/approve state at all** — a parsed row is live immediately (deliberate, documented design choice in `schedule_ingest.py`'s own module docstring) |
| Generic operational receipt | `Receipt` (`models.py:879`) | `db.receipts` | `receipts.py` (+ in-process `create_receipt`/`update_receipt_status` called from tasks/transportation/resident_requests/alerts/residents/devices/admin_assistant/resident_activation) | Mutates the most-recent receipt in place on a status change — see §18 |
| Telemetry/trace log | `CaosEvent` (`models.py:914`) | `db.events` | `events.py` (+ `log_event()` called only from `admin_assistant*`, `realtime_diagnostics`, `devices`) | **Not** called from `tasks.py`/`alerts.py`/`transportation.py` — confirmed by grep, so most operational lifecycle transitions are NOT in `db.events`, only in `db.receipts` |
| Departments | `Department` (`models.py:987`) | `db.departments` | `departments.py` | Seeded at startup (`seed_default_departments()`), admin-editable |
| Staff/roles | `User` (`models.py:111`) | `db.users` | `staff.py`, `auth.py` | `department: Optional[str]` — **now settable** (was the 2026-09-06 audit's P0 #1, now closed) |
| Aria's own operational-state unification | n/a | reads `db.alerts` + `db.staff_tasks` | `aria_operational_state.py::resolve_operational_state()` | Built for Aria's prompt context only — never called from any Admin/Live Board route (verified: `grep -rn "resolve_operational_state" frontend/ backend/routes/ops_overview.py backend/routes/alerts.py` → zero hits outside the `aria_*`/`realtime_*` modules) |

---

## 3. WORKFLOW STATE MATRIX (states that actually exist, not aspirational)

| Workflow | Model.field | States that exist | Missing vs. the target NEW→ACK→ASSIGNED→IN-PROGRESS→CLOSED lifecycle |
|---|---|---|---|
| Generic StaffTask / resident request / department work | `StaffTask.status` (`TaskStatus`, `models.py:748`) | `pending → in_progress → completed \| skipped` | No `acknowledged`/`claimed`/`assigned` **status** — `acknowledged_at`/`assigned_to` are separate fields that can be set independently of `status`, so "acknowledged" and "assigned" are facts recorded on the object, not points in the status enum. No `cancelled` (only `skipped`). No `escalated`. |
| Maintenance work order (same `StaffTask`, `visibility_role="maintenance"`) | same as above | same 4 states | Per `ADMIN_OPERATIONS_AUDIT.md` §11 (re-verified, unchanged): no `blocked`/`waiting_parts`/`waiting_vendor`/`verified` |
| Resident-assistance event | `Alert.status` (`AlertStatus`, `models.py:259`) | `active → acknowledged → resolved` | No `escalated` **in the enum**, even though `escalation.py::tick` writes `status: "escalated"` and queries `status in [open, active, acknowledged, escalated]` — `"open"` and `"escalated"` are not valid `AlertStatus` values (confirmed: `models.py:259` literal is exactly `["active","acknowledged","resolved"]`). This is a real, live inconsistency, not fixed since the 2026-09-06 audit. |
| Level-1 event lifecycle (layered on `Alert`) | `Alert.aria_state` (`AriaState`, `models.py:279`), `Alert.live_line_state` (`LiveLineState`, `models.py:280`) | `aria_state`: dormant/active/muted_staff/dismissed. `live_line_state`: none/offered/ringing/connected/declined/no_answer | These are richer than plain `status` but are a SEPARATE state machine layered on the same document — three quasi-independent state fields (`status`, `aria_state`, `live_line_state`) plus `activation_consumed_at` on one `Alert` (§5) |
| RF activation coalescing (not a status — an open/consumed boundary) | `Alert.activation_consumed_at` | `None` (open) → set (consumed) | Deliberately NOT the same axis as `status` (`models.py:306-315` comment explains why) — a resolved incident that never got a voice session can still be `status=active` |
| Transportation run | `TransportRun.status` (`RunStatus`, `models_transportation.py:25`) | `confirmed → in_progress → completed \| cancelled` | No `assigned`/`unassigned` distinction in the enum — `driver_id`/`vehicle_id` are `Optional`, so a `confirmed` run can have neither (confirmed by direct query, §6) |
| Receipt (generic action ledger) | `Receipt.status` (`ReceiptStatus`, `models.py:876`) | `created → acknowledged → in_progress → completed \| failed \| cancelled` | The richest enum in the system, but `update_receipt_status()` overwrites the MOST RECENT receipt for an object rather than appending a new one — see §18 |
| RF transmission semantics | `RfClass` (`rf_semantics.py`) | `help_press \| supervisory \| tamper \| battery_status \| unknown` | Not a workflow status — a classification gate. Only `help_press` may create/attach to a resident-assistance event (`ACTIVATION_CLASS = "help_press"`, `rf_semantics.py:50`) |

---

## 4. UI → API → DATABASE TRACE

Table format: **Screen** → **frontend calls** → **backend route** → **collection(s)**. "Live/poll" column cites the exact interval.

| # | Screen | Frontend file | API calls | Backend route(s) | Collection(s) | Poll |
|---|---|---|---|---|---|---|
| 1 | Live Board / Staff Dashboard | `StaffDashboard.jsx:57,73` | `GET /alerts/feed`, `GET /alerts/stats`, `GET /locations/latest`, `GET /insights/summary` | `alerts.py::alerts_feed/alert_stats`, `location.py`, `insights.py` | `db.alerts`, `db.locations`, `db.insights` | **3000ms** (`StaffDashboard.jsx:73`) |
| 2 | Community → Operations overview | `OperationsOverview.jsx:34` | `GET /ops/overview` | `ops_overview.py::operations_overview` | `db.staff_tasks`, `db.alerts`, `db.departments` (read) | 30000ms |
| 3 | Community → Alerts & events | `AlertsBoard.jsx:52` | `GET /alerts`, `GET /alerts/{id}` (detail dialog) | `alerts.py::list_alerts/get_alert` | `db.alerts` | 15000ms |
| 4 | Community → Maintenance | `MaintenanceWorkspace.jsx:51` | `GET /tasks?visibility_role=maintenance`, `POST /tasks/{id}/{acknowledge,start,complete}`, `POST /tasks/{id}/assign` | `tasks.py`, `task_assignment.py` | `db.staff_tasks` | 20000ms |
| 5a | Resident Hub → Overview | `ResidentHubPanels.jsx:34-35` | `GET /residents/{id}/briefing`, `GET /residents/{id}/stats` | `resident_analytics.py` | `db.residents`, `db.alerts` (aggregated), `db.staff_tasks` | on-open only, no poll |
| 5b | Resident Hub → Conversations | `ResidentHubPanels.jsx:84` | `GET /residents/{id}/conversation-sessions` | `resident_conversations.py` | `db.conversations`, `db.realtime_diagnostics` | on-open only |
| 5c | Resident Hub → Assistance events | `ResidentHubPanels.jsx:127` | `GET /alerts?limit=500` **(no server-side `resident_id` filter — client filters 500 rows in JS)** | `alerts.py::list_alerts` | `db.alerts` | on-open only |
| 5d | Resident Hub → Resident requests | `ResidentHubPanels.jsx:182` | `GET /tasks?resident_id=` | `tasks.py::list_tasks` | `db.staff_tasks` | on-open only |
| 5e | Resident Hub → Memory | `MemoryDialog.jsx` (now `MemoryPanel`) | `GET/POST/PATCH/DELETE /memory` | `memory.py` | `db.memories` | on-open only |
| 5f | Resident Hub → Movement | `MovementDialog.jsx` (now `MovementPanel`) | `GET /residents/{id}/movement?hours=` | `resident_analytics.py` | `db.locations` | on-open only |
| 5g | Resident Hub → Device | `ResidentHubPanels.jsx:227` | `GET /rf/fleet/summary`, filtered client-side by `resident_id` | `rf_fleet.py` | `db.rf_devices` | on-open only |
| 6 | Departments & Staff + queues | `DepartmentsTab.jsx`, `DepartmentWorkspace.jsx:103` | `GET/POST/PATCH/DELETE /departments`, `GET /tasks?visibility_role=<slug>`, `PATCH /staff/{id}` (department) | `departments.py`, `tasks.py`, `staff.py` | `db.departments`, `db.staff_tasks`, `db.users` | 15000ms (workspace) |
| 7a | Resident requests | `RequestsBoard.jsx` | `GET /tasks` (client-filters `source != "staff"`) | `tasks.py::list_tasks` | `db.staff_tasks` | poll not found — re-fetches on action only (verified: no `setInterval` in `RequestsBoard.jsx`) |
| 7b | Tasks | `TasksTab.jsx:38-47` | `GET /tasks` (**no `day=` filter ever sent — see §6**), `GET /tasks/templates/all`, `POST /tasks/spawn-today` | `tasks.py`, `task_templates.py` | `db.staff_tasks`, `db.task_templates` | "My tasks" sub-widget polls 10000ms (`TasksTab.jsx:348`); main list has none |
| 7c | Schedule | `ScheduleTab.jsx` | `GET/POST/PATCH/DELETE /schedule` | `schedule.py` | `db.schedule_items` | none found |
| 7d | Menu | `MenuTab.jsx` | `GET /menu`, `GET /menu/uploads`, `POST /menu/uploads/{id}/approve`, `POST /menu/ingest/dev-test` | `menu.py`, `menu_ingest.py` | `db.menu_items`, `db.menu_uploads` | none found |
| 7e | Transportation | `TransportationTab.jsx` | `GET /transportation/report` (single day) | `transportation_report.py` | `db.staff_tasks` (category=transportation), `db.transport_runs` | none found (manual refresh) |
| 7f | Transport calendar | `TransportationCalendar.jsx` | `GET /transportation/calendar?date=&days=` | `transportation_calendar.py` | `db.transport_runs` | none found |
| 7g | Transport resources | `TransportResourcesTab.jsx` | `GET/POST/PATCH/DELETE /transportation/{drivers,vehicles}`, `/scheduling-config` | `transportation_resources.py` | `db.transport_drivers`, `db.transport_vehicles`, `db.transport_scheduling_config` | none found |
| 8a | Pendants | `RFPairingTab.jsx:47,226,364` | `GET /rf/devices`, `/rf/events`, `/rf/bridges/active`, `POST /rf/pair` | `rf.py`, `rf_bridge_health.py` | `db.rf_devices`, `db.rf_events` | 6000ms + two inner 226/364 intervals during active pairing flows |
| 8b | Wearables | `WearablesTab.jsx` | `GET/POST/PATCH/DELETE /wearables` | `wearables.py` | `db.wearables` | none found |
| 8c | Smart devices | `DevicesTab.jsx` | `GET/POST/PATCH/DELETE /devices`, `POST /devices/{id}/command` | `devices.py` | `db.smart_devices`, `db.device_commands` | none found (Admin); resident kiosk polls devices every 10000ms (`Kiosk.jsx:187`) |
| 8d | Kiosks | `KiosksTab.jsx` | `GET/POST/PATCH/DELETE /kiosks` | `kiosks.py` | `db.kiosks` | none found |
| 8e | Device tokens | `DeviceTokensTab.jsx` | `GET/POST/DELETE /device-auth` | `device_auth.py` | `db.device_tokens` | none found |
| 8f | Hardware receipts | `HardwareReceiptsTab.jsx` | `GET/POST /hardware/*` | `hardware.py` | `db.hardware_devices`, `db.hardware_receipts` | none found |
| 9a | Ops reports | `ReportsTab.jsx` | `GET /reports/daily-exceptions`, `/weekly-workload` | `reports.py` | `db.staff_tasks`, `db.alerts`, `db.receipts` | manual (date-range picker), no poll |
| 9b | Activity log | `ActivityLog.jsx` → `ReceiptsPanel.jsx`/`EventsPanel.jsx` | `GET /receipts`, `GET /events` | `receipts.py`, `events.py` | `db.receipts`, `db.events` | manual, no poll |
| 9c | Insights | `Insights.jsx` | `GET /insights`, `GET /insights/summary`, `POST /insights/compute` (manual) | `insights.py` | `db.insights` | manual recompute only — `delete_many({})` then rebuild, no history kept |
| 9d | Audit | `AuditTab.jsx` | `GET /audit/summary`, `/audit/{alerts,tasks,pages,medications}.csv` | `audit.py` | multiple, CSV export | manual |
| 9e | Escalation | `EscalationTab.jsx` | `GET/PUT /escalation/rule`, `POST /escalation/tick` (manual button) | `escalation.py` | `db.escalation_rules`, `db.alerts` | none — **tick has no automatic caller anywhere**, confirmed §13 |
| 10 | Clinician dashboard | `ClinicianTab.jsx` | `GET /residents/{id}/stats` | `resident_analytics.py` | `db.alerts` (aggregated) | none found; "AI summary" card reads `stats.narrative`, which `/stats` never returns (only `/briefing` does) — unchanged from the 2026-09-06 audit, re-verified: `grep -n "narrative" backend/routes/resident_analytics.py` → no match in the `/stats` handler |

**Read-only screens despite existing mutation endpoints (item E):** Department workspace inside `DepartmentsTab.jsx` (the admin-only `DepartmentWorkspaceDialog`) still only lists tasks — `POST /tasks/{id}/assign` and `/acknowledge|start|complete` exist and are used elsewhere (`MaintenanceWorkspace.jsx`, `RequestsBoard.jsx`) but are not wired into that dialog. Insights has `POST /insights/compute` but nothing calls it automatically. Escalation has `POST /escalation/tick` with the same gap.

**UI actions that don't complete the real workflow (item F):** None found beyond the above — every action button traced (Acknowledge/Start/Complete/Assign/Approve/Resolve) does call its real backend endpoint and persists to the cited collection. The complaint "doesn't feel like one system" is a data/consistency problem (§6), not fake buttons.

**Why Tasks can't be opened/edited (item G):** `TasksBoard` (rendered inside `TasksTab.jsx`) offers Start/Complete/Skip actions per row but has no row-click-to-detail affordance and no `PATCH` call wired to any edit form — `PATCH /tasks/{task_id}` exists in `backend/routes/tasks.py:145` (title/description/priority/etc.) but `grep -n "api.patch(\`/tasks" frontend/src/pages/TasksTab.jsx` returns nothing. Compare to `RequestsBoard.jsx` + `RequestDetailDialog.jsx`, which DO open a detail dialog with acknowledge/start/complete and a resident-visible schedule/note editor calling the same `PATCH /tasks/{id}`. **The capability exists in one sibling screen and is simply not reused in `TasksTab.jsx`.**

---

## 5. DUPLICATED OR COMPETING SOURCES OF TRUTH

- **Two escalation implementations that disagree** (unchanged from 2026-09-06, re-verified): `alerts.py::alerts_feed` does inline escalation at 60/180/420s with levels 0-3; `escalation.py::tick` uses rule-configured `level_2_seconds`/`level_3_seconds` (default 90/150) and writes `status: "escalated"` — a value `AlertStatus` doesn't contain (`models.py:259`). Two clocks, two thresholds, one field, one of them writing an invalid value.
- **`Alert` doubles as `ResidentEvent`** — one document carries `status` (staff workflow), `aria_state` (voice-session state), `live_line_state` (phone-routing state), and `activation_consumed_at` (kiosk-relaunch boundary) as four quasi-independent axes. This is by design (documented in `models.py:306-321`) and is NOT recommended for merging further — see §7 for why it should be preserved as-is.
- **Layer E (`aria_operational_state.py::resolve_operational_state`) already does, for Aria, exactly what the Live Board needs to do for humans** — unify open `db.alerts` + open `db.staff_tasks` per resident into one lifecycle-normalized snapshot — but it is a completely separate code path from `ops_overview.py`'s attention list. They do not call each other. Building a human-facing Live Board aggregation without reusing this function would be the THIRD independent "what's open right now" implementation (the first two: `ops_overview.py`'s attention ranking, and `alerts.py::alerts_feed`'s inline escalation view).
- **`GET /alerts` has no `resident_id` filter** (`alerts.py:100-118`) — `ResidentHubPanels.jsx:127` works around this by fetching `limit=500` and filtering client-side. Functions today (337 total alerts, under the 500 cap) but is a real gap, not a pattern to copy.
- **Two duplicate-detection mechanisms, correctly NOT merged** — `resident_activation.py::record_resident_activation()` (resident-assistance events, RF/kiosk-button) and `resident_requests.py::create_resident_request()`'s inline dedup (StaffTask requests). These operate on different collections for different reasons and should stay separate (see §12) — flagging only so a future pass doesn't conflate them.
- **Two transportation representations coexist**: the resource-aware `TransportRun`/driver/vehicle engine (current) and the legacy hourly `TransportSlot` bucket (`transportation_legacy_slots.py`, historical data only, 2026-08-09 through 2026-09-04, superseded 2026-08-22 per `PROJECT_STATE.md`). Not a live conflict — the legacy path is not written to by current code — but a stale-looking read source if anyone queries `db.transport_slots` expecting current state.

---

## 6. STALE/DEMO DATA CAUSES — quantified (item I)

Read-only counts against the live EliteDesk `caoscare` database, 2026-09-20:

| Metric | Count | Source query |
|---|---|---|
| `db.alerts` total | 337 | `count_documents({})` |
| `db.alerts` `status="active"` | **319** | `count_documents({"status":"active"})` |
| `db.alerts` `status="acknowledged"` | 2 | |
| `db.alerts` `status="resolved"` | 16 | |
| Open alert age: minimum | **341.7 hours** (~14.2 days) | computed from `created_at` on all 321 open alerts |
| Open alert age: maximum / median | 1010.6h (~42 days) / 533.4h (~22 days) | |
| Open alerts with age ≤ 24h | **0** | none of the 321 open alerts are actually recent |
| Open alerts by room (top) | room `401`: 272, `test`: 31, `TEST-101/201/202`: 3/3/2, `121`/`403`/`408`: 2-3 each | these are the historical RF-bench-test/Level-1-forensics rooms documented across `PROJECT_STATE.md`'s 2026-08-29/30 and 2026-09-06 entries, not live resident rooms in current use |
| `db.staff_tasks` total / open | 85 / 62 | |
| `db.menu_items` for 2026-09-20 (any status) | **0** | most recent menu date in this DB is **2026-09-13** (distinct dates span 2026-08-22→2026-09-13, 22 days) |
| `db.schedule_items` for 2026-09-20 | **0** | most recent schedule date in this DB is **2026-09-05** (distinct dates span 2026-08-23→2026-09-05) |
| `db.transport_runs` | does not appear in `list_collection_names()` (0 or never-created) | the resource-aware engine has never been exercised against real data in THIS database |
| `db.transport_slots` (legacy) distinct dates | 27 dates, span 2026-08-09→2026-09-04 — **entirely in the past** relative to 2026-09-20 | |
| Open transportation `StaffTask`s | 15, **all 15 have `requested_for_date` on or before 2026-09-08** (12+ days stale) | |
| `past_requested_date_open` (ops_overview's own computed field) | **14** | |
| `needs_action` (open + unbooked transportation, ops_overview's own field) | **11** — **matches the user's reported "11 old unresolved transportation items" exactly** | |
| `staff_tasks` with `created_at` starting with today's date | **0** | |
| Demo-tagged records present (from `seed_demo_community.py`) | 5 `staff_tasks` in `3W0x` rooms, 10 residents named `Demo - *` | still present, correctly isolated by the naming convention (see §19) |

**Root causes, each independently confirmed by reading the source:**

1. **"Hundreds of ACTIVE events" (item A):** `GET /alerts/stats` (`alerts.py:302-319`, the exact endpoint `StaffDashboard.jsx:57` calls into `AlertStatsRow.jsx`'s "Active" tile) is `count_documents({"status":"active"})` with **zero age filter of any kind**. It returns the literal, unfiltered count of every `Alert` document ever created with `status="active"` that nobody has ever acknowledged/resolved — 319 today, virtually all multi-day-old RF pendant-test debris from the 2026-08-29 through 2026-09-06 Level-1 hardware testing sessions (`PROJECT_STATE.md` itself flags "319 active alerts, mostly stale RF-test debris" across three separate September entries — this audit confirms the number is unchanged today). `ops_overview.py`'s attention list is slightly better — it demotes anything >72h to the bottom tier (`STALE_HOURS=72`, `ops_overview.py:32,197-204`) and labels it "likely stale test data" in `COUNTS_CAVEAT` (`ops_overview.py:35-38`) — but its own top-line `assistance.active`/`assistance.open_total` counters are **also unfiltered by age** (`ops_overview.py:106-116`), so the same 319/321 number surfaces there too, just with a caveat string attached.
2. **Empty menu/schedule for 2026-09-20 (item I):** this EliteDesk's own local `caoscare` database was never fed data past 2026-09-13 (menu) / 2026-09-05 (schedule). `PROJECT_STATE.md`'s 2026-09-19 entry ("Room 214 kiosk real-usability pass") documents this directly and explicitly chose to make the resident-facing kiosk (`TodayPanel.jsx`) read production's live menu/schedule via an opt-in `REACT_APP_FACILITY_CONTENT_URL` env var instead of fixing EliteDesk's own local data. That env var affects only the resident kiosk's `TodayPanel` component — Admin's `MenuTab.jsx`/`ScheduleTab.jsx` still read this same local, stale database directly, so Michael sees empty results in Admin even though the kiosk shows real content.
3. **11 old transportation items (item I):** confirmed exact match — every currently-open transportation `StaffTask` was created 2026-08-10 through 2026-09-07 and every one's `requested_for_date` is in the past. No new transportation requests have been created in this database since 2026-09-07.
4. **"Old demo/test tasks under Today" (item I):** `TasksTab.jsx`'s "Today" tab (`TasksTab.jsx:34,76`) is **not date-filtered at all** — `fetchAll()` (`TasksTab.jsx:38-46`) calls plain `GET /tasks` with no query parameters, even though the backend already supports `day: Optional[str]` (`backend/routes/tasks.py:72,97-99`). The tab literally labeled `Today (${tasks.length})` shows every one of the 85 `staff_tasks` documents regardless of age. This is a UI mislabeling gap, not a data problem — the backend filter exists and is simply never invoked.
5. **Hundreds of stale assistance exceptions:** direct consequence of #1 — every report/overview that sums "open alerts" inherits the 319/321 unfiltered figure unless it explicitly age-filters (only `reports.py::daily-exceptions` does this correctly, per §9a below, by only counting the SPECIFIC alerts still open on the report's target date's own tier logic — not independently re-verified line-by-line in this pass, flagged for confirmation).

---

## 7. EXISTING CAPABILITIES TO PRESERVE

- **RF help_press vs. supervisory semantic distinction is real, implemented, and already enforced today** — `backend/routes/rf_semantics.py::classify_transmission()`, wired into `backend/routes/rf_matched_intake.py:56,99` (`if rfclass.semantic != ACTIVATION_CLASS: <do not activate>`). This is exactly what the pilot's pendant-scope constraint asks to preserve. Live-evidenced 2026-09-06/07 per the module's own docstring (help_press = switch5 CLOSED, long multi-frame burst; supervisory = all switches OPEN, short ~64-67min-periodic burst). **Do not build a second classifier or bypass this gate for the simulator or any new feature.**
- **`record_resident_activation()`** (`resident_activation.py`) — the generalized "one open incident per resident, repeat presses/button-taps attach to it, don't spawn a new one" rule, already resident-scoped (not device-scoped) since the 2026-09-06 Level-1 directive. This is the correct, single mechanism for "did a NEW resident-assistance event just start" — any simulator or new UI path must call this function, not write `db.alerts` directly.
- **`resident_requests.py::create_resident_request()`'s duplicate/re-request detection** — see full trace in §12. Real, working, in production use.
- **The `StaffTask` Claim(assign)→Start→Complete pattern** (`task_assignment.py::POST /tasks/{id}/assign`, `tasks.py::POST /tasks/{id}/{acknowledge,start,complete}`) — a real, working, receipt-backed state-transition pattern already proven for Maintenance. See §11 for reuse assessment.
- **Layer E's operational-state unification** (`aria_operational_state.py::resolve_operational_state`) — already solves the exact "one lifecycle vocabulary across alerts+tasks" problem the Live Board needs; currently serves only Aria's own prompt, not any human screen. Reusing it (read-only) is the lowest-risk way to make Live Board and Aria agree, ever.
- **`create_receipt()`/`update_receipt_status()`** — the one real cross-domain event-logging primitive, already called from 8+ modules. Any new feature (simulator included) should call this, never invent a second logging table.
- **Transportation's resource engine** (`transportation_engine.py`) — the most complete department implementation; its `find_or_create_run()` pattern (deterministic, defaults to "pending, needs a human" under any uncertainty) is the right template for how a simulator should behave under ambiguity too.
- **The `Alert.event_log[]` per-transition array** (`{at, field, from, to}`, `models.py:329`) — genuinely IS a state-transition audit trail already, contrary to an assumption that only `StaffTask` needed one. Preserve this shape; it's the right pattern for §18's replay question, and `StaffTask` should probably get the equivalent (see §8).

---

## 8. MISSING OPERATIONAL LINKS

- **No `resident_id` filter on `GET /alerts`** (§5) — `ResidentHubPanels.jsx` works around it with an inefficient client-side filter over `limit=500`.
- **`StaffTask` has no per-transition history array** — only named timestamps (`created_at`, `acknowledged_at`, `started_at`, `completed_at`, `last_re_requested_at`). A task that is started, stopped, reassigned, and restarted leaves no record of the intermediate reassignment or the fact it was ever paused (`Alert.event_log[]` has this; `StaffTask` does not).
- **`log_event()`/`db.events` coverage is narrow** — only `admin_assistant*`, `realtime_diagnostics`, `devices` call it. Task/alert/transportation lifecycle only exists in `db.receipts`, and `update_receipt_status()` (§18) overwrites rather than appends, so `db.receipts` is not a full replay source either for those domains.
- **`TasksTab.jsx`'s "Today" tab ignores the backend's own `day=` filter** (§6#4) — a one-line frontend fix, not a backend gap.
- **`AlertStatus` enum is missing `"escalated"`, which `escalation.py::tick` writes anyway** (§3, §5) — a genuine, live data-integrity bug (writes a value outside the model's own declared literal).
- **`DepartmentWorkspaceDialog` (inside `DepartmentsTab.jsx`) is read-only** despite `POST /tasks/{id}/assign` and the ack/start/complete endpoints existing and being used by its sibling `MaintenanceWorkspace.jsx` — confirmed by inspecting `DepartmentWorkspaceDialog.jsx` for any mutation call: none found.
- **`GET /tasks` has no server-side "created since X" or "requested_for_date >= today" filter used by any UI** even though the model has the fields to support one — every "old items under Today/Transportation" symptom traces back to a screen simply not passing a filter that could be passed.
- **No automatic caller for `POST /escalation/tick` or `POST /insights/compute`** (§13) — both require an admin to click a button.

---

## 9. LIVE BOARD INTEGRATION OPTIONS (report-only — no build)

Given §5's finding that Layer E already does the real unification work for Aria:

- **Option A (lowest risk): Live Board calls `resolve_operational_state()` per open item**, read-only, to render a lifecycle badge that is guaranteed to agree with whatever Aria would say about the same item in the same moment. Does not change `db.alerts`/`db.staff_tasks` write paths at all.
- **Option B: extend `ops_overview.py`'s own attention list to exclude (not just demote) alerts older than a configurable threshold from the raw `assistance.active`/`open_total` counters**, keeping the full historical count available under a separate, explicitly-labeled "all-time" field. This directly fixes item A/§6 without touching Layer E or the write path at all — the smallest possible change.
- **Option C: a genuinely new "attention" aggregation function that supersedes both** — explicitly NOT recommended per the user's own instruction not to build a second competing source of truth; only worth considering if A and B both prove insufficient after being tried.

---

## 10. FRONT-DESK / STAFF COMMUNICATION OPTIONS (traced, not proposed)

| Mechanism | Code | Live-configured in this EliteDesk `.env`? |
|---|---|---|
| SMS (escalation) | `escalation.py::_try_sms` (`escalation.py:130-135`), reads `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_FROM_PHONE` | **No** — none of these three vars are present in `backend/.env` at all (confirmed: `grep -E "^TWILIO_ACCOUNT_SID=|^TWILIO_FROM_PHONE="` returns nothing) |
| Voice call (live-line "someone is asking for help now") | `resident_activation.py::try_call_on_call_phone()` (`resident_activation.py:255-274`) — reads `facility.on_call_phone` + the same three Twilio vars, falls back to `log.info(...)` no-op if any are missing | **No** — same as above; degrades to a log line only |
| Email (department notification on new request) | `notifications.py::send_email` (reads `RESEND_API_KEY`/`RESEND_FROM_EMAIL`) — this IS the real path `notify_department()` uses for every new `StaffTask`/resident request | **No** — `RESEND_API_KEY` absent from this `.env`; degrades to `status: "logged"`, no real email sent |
| Real inbound email (menu/activities ingestion) | `email_inbound.py` (this session's own prior work, commit `e092e36`) — Svix-verified webhook, fails closed (503) with no `RESEND_WEBHOOK_SECRET` | **No** — not configured; endpoint present, correctly inert |

**Conclusion for item N:** every notification/call transport CAOSCare has code for degrades to a harmless logged no-op in this environment today. Nothing is fabricated or falsely claimed live by the code (each path's own `doc["status"]="logged"` is honest about this). For the pilot's stated communication constraint (CAOSCare-owned laptop/tablets + VoIP/telephone + email as *adapters*, never the canonical database), the code shape already matches that intent — `notify_department()` sends a *notification about* a `StaffTask` that already exists in `db.staff_tasks`; it never uses email as the record of truth. **What's missing is credentials, not architecture.**

---

## 11. LOWEST-RISK IMPLEMENTATION ORDER

1. Fix `TasksTab.jsx` to pass `day=<facility_today>` (or an explicit "all" toggle) — one-line frontend change, zero backend risk, directly fixes the "old demo tasks under Today" complaint (§6#4).
2. `ops_overview.py`: exclude (not just demote) `age > STALE_HOURS` alerts from the raw `assistance.active`/`open_total` counters, keep the current number available as a separate labeled field (§9 Option B) — small, isolated to one file.
3. Reconcile the `AlertStatus` literal / `escalation.py::tick` mismatch (add `"escalated"` to the enum, or stop `tick` from writing an unmodeled value) — a real correctness bug, low blast radius, but touches the same file the Level-1/Aria lane owns per `ADMIN_OPERATIONS_AUDIT.md`'s own coordination note — confirm ownership before touching.
4. Wire `DepartmentWorkspaceDialog` to the already-existing `assign`/`acknowledge`/`start`/`complete` endpoints (reuse `MaintenanceWorkspace.jsx`'s pattern) — makes the department queues actionable without any new backend code.
5. Refresh EliteDesk's own local menu/schedule data for the current date window using the already-existing idempotent seed scripts (`seed_menu_two_weeks.py`, `seed_schedule_two_weeks.py`) — pure data operation, zero code risk, directly fixes the empty-Menu/Schedule-tab symptom in Admin (separate from the kiosk's own already-working production-read workaround).

---

## 12. EXISTING DUPLICATE-REQUEST / IDEMPOTENCY PATH (full trace)

**Function:** `backend/routes/resident_requests.py::create_resident_request()`, lines 78-194, called from `POST /api/tasks/resident-request` (public, no-auth — same trust model as `/alerts`).

**Matching criteria (exact, `resident_requests.py:107-115`):**
```python
dup_q = {"category": data.category, "status": {"$in": ["pending", "in_progress"]}}
if data.resident_id:      dup_q["resident_id"] = data.resident_id
elif data.room:           dup_q["room"] = data.room
else:                     dup_q = None   # no dedup possible — no identity on either side
existing = db.staff_tasks.find_one(dup_q, sort=[("created_at", -1)])   # most recent match wins
```
So the match key is **category + (resident_id, falling back to room) + open status** — nothing else. It explicitly does **not** consider: the actual problem/content of the request (`resident_words`/`summary`), priority, `conversation_session_id`, or how long ago the existing one was opened.

**What happens on a match:** no second `StaffTask` is created. The existing task's `re_request_count` is incremented and `last_re_requested_at` is set (`resident_requests.py:130-135`); a new `Receipt` (`action_type="resident_request_re_requested"`) is filed against the SAME task; the department is re-notified with a "REPEAT request" subject line; the response returns `duplicate: true`, `re_request_count`, and — critically — `existing_summary` + a boolean `same_issue` (a string-equality check between the new and existing `resident_words`/`summary`, added 2026-08-27 after a real incident where two genuinely different problems in the same category collided and Aria falsely claimed they were the same request, `resident_requests.py:118-129`).

**How Aria is told:** the same HTTP response also carries `lifecycle`/`opened_age`/`spoken` (via `request_status_view()` in `aria_request_status.py`, which is built on Layer E's `task_lifecycle()` — so the duplicate response cannot contradict what Layer E would separately tell Aria about the same task). Aria's tool-calling code (`realtimeOperationsTools.js`) surfaces `spoken` verbatim rather than re-deriving language from raw `status`.

**Reusing it for a front-desk human-entry path — concrete assessment:** the dedup logic itself (lines 107-163) is a pure, reusable block of code. The one concrete blocker today is `create_resident_request`'s own input validation: `if data.source not in ("aria_voice", "kiosk_button"): raise HTTPException(400, "Invalid source")` (`resident_requests.py:96-97`). A front-desk caller has no valid `source` value to pass. Two viable, non-duplicating options: **(a)** add `"front_desk"` (or reuse the existing `"staff"` `TaskSource` value) to that allowed-sources check and require auth (`Depends(get_current_user)`) on a front-desk-facing variant of the same function — the dedup query, receipt, and notification logic do not need to change at all; **(b)** extract lines 107-163 into a small shared helper (`find_or_bump_duplicate_request()`) callable from both the existing public endpoint and a new authenticated one, if the two call sites' auth/response shape need to diverge further later. Either way: **the existing function/logic is reused, not reimplemented** — this repo's own convention (per `email_inbound.py`'s `create_menu_upload`/`create_schedule_items` extraction pattern, done this same session) is exactly option (a)/(b)'s shape.

`POST /tasks` (plain admin/staff task creation, `tasks.py:108-142`) — the OTHER existing "create a StaffTask" path a front-desk person might currently use — has **zero duplicate-detection of any kind**, confirmed by reading the full function: it always inserts unconditionally. This is the concrete gap: if front-desk staff create requests via `TasksTab`'s "New task" dialog today, they get no duplicate warning at all, unlike a request that comes in through Aria/kiosk.

---

## 13. CURRENT BACKGROUND/TIME-BASED PROCESSING

**Confirmed absent, exhaustively.** `grep -rniE "apscheduler|BackgroundScheduler|croniter|schedule\.every|celery|while True:" backend/` (excluding tests) returns **zero matches**. The only `asyncio.create_task()` calls in the entire backend (`alerts.py:295`, `ai.py:262`, `realtime_memory_ingest.py:86`) are fire-and-forget continuations of a SINGLE already-in-flight HTTP request (alert AI-classification, a chat response, memory extraction) — none are periodic or time-driven. No crontab entry, systemd timer, or deployment-script cron line references this application (`crontab -l`, `systemctl --user list-timers`, and `grep` over `docs/DEPLOYMENT_RUNBOOK.md`/`scripts/` all confirm nothing). `POST /escalation/tick` and `POST /insights/compute` are the only time-relevant operations that exist, and both are manual-only (admin clicks a button) — there is no automatic caller anywhere in this codebase or its deployment configuration. **CAOSCare currently has no notion of "time passing while nobody is looking."**

---

## 14. LIVING-BUILDING SIMULATION ARCHITECTURE OPTIONS (report-only)

No simulation engine, scenario runner, demo clock, or event generator exists anywhere in this repository — verified by grepping `backend/`, `backend/scripts/`, and `docs/` for any of those terms plus `simulate`/`simulator`/`synthetic` beyond the already-known one-shot seed scripts (`seed_demo_community.py`, `seed_mock_devices.py`, `seed_transportation_pilot.py`, `seed_menu_two_weeks.py`, `seed_schedule_two_weeks.py`, `seed_mock_residents.py`, `seed_demo_announcements.py`, `seed_department_engagement.py`) and the resident-kiosk's own `POST /locations/mock/generate` (a single synthetic-location-ping generator, `location.py`, triggered by a "Simulate" button — the closest thing to a "generator" that exists, and it is one-shot per click, not continuous).

If built (NOT built in this pass), the correct shape per the codebase's own architecture is a driver process/script that calls the SAME functions real callers use, never writes `db.*` directly:

- Resident voice request → `resident_requests.py::create_resident_request()` (the exact function traced in §12 — a simulated request gets the SAME dedup/receipt/notification behavior a real one does, for free).
- Front-desk-created request → the same function once (a) or (b) from §12 exists, or `POST /tasks` (`tasks.py::create_task`) for plain staff-originated work.
- Maintenance claim/start/complete → `task_assignment.py::POST /tasks/{id}/assign` + `tasks.py::POST /tasks/{id}/{start,complete}`.
- Pendant help_press → **must go through `rf_semantics.classify_transmission()` and `resident_activation.py::record_resident_activation()`**, not a direct `db.alerts.insert_one()` — this is the one place a naive simulator could accidentally bypass the exact RF semantic gate the pilot explicitly wants preserved (§7). The cleanest reuse is calling `record_resident_activation()` directly with a synthetic but correctly-shaped `help_press`-classified event, rather than re-simulating raw RF frames through `rf_matched_intake.py`.
- Transportation booking → `transportation_engine.py::find_or_create_run()` (the same deterministic, defer-to-pending-under-uncertainty engine real requests use).
- Escalation → `escalation.py::tick()` called by the simulator's own clock loop (this is, notably, the ONE existing function that is already built exactly for a scheduler to call — it has simply never had one).
- Menu/schedule changes → `menu_ingest.py::create_menu_upload()` / `schedule_ingest.py::create_schedule_items()` (the same functions this session's real inbound-email adapter calls — already proven reusable by two different real callers).
- Receipts/audit → automatic, since every function above already calls `create_receipt()` internally.

---

## 15. CURRENT-TIME EVENT GENERATION PLAN (report-only sketch)

Not built. If built: a single process reading the real wall clock (`routes/realtime_facility.py::today_facility_date()`/`_facility_now()` — already the one source of "what time is it at the facility," reused rather than duplicated), holding a small in-memory or `db`-persisted schedule of "next event at time T, call function F with args A," advancing only forward from wherever it last left off (so a restart resumes rather than replaying). No new time-abstraction needed — `now_utc()` (`models.py`) is already the single clock every model uses.

## 16. STAFF/DEPARTMENT SIMULATION MODEL (report-only sketch)

Not built. The real `User` model already has `department: Optional[str]` (now settable, §-header) and `role` (`owner|admin|staff|front_desk`). A simulation would need a small set of REAL `User` documents (e.g. 4-6, one or two per department) created through the real `POST /staff` endpoint — not fabricated documents — so that `assigned_to`/`assigned_name`/`acknowledged_by`/`completed_by` on every simulated `StaffTask`/`Alert` point at genuine, queryable staff accounts. `Department.slug` already provides the routing target list (`get_active_departments()`).

## 17. REAL-TIME LIVE BOARD UPDATE OPTIONS

No push mechanism (WebSocket/SSE/Mongo change stream) exists anywhere — confirmed by grep, zero matches for `websocket`, `EventSource`, `.watch(` against pymongo/motor cursors. **However**, `StaffDashboard.jsx` already polls every **3000ms** (`StaffDashboard.jsx:73`) and `PagerFeedCard.jsx` every 3000ms — both already close to real-time in practice. The actual inconsistency is that OTHER screens poll much slower or not at all (`OperationsOverview.jsx` 30000ms, `MaintenanceWorkspace.jsx` 20000ms, `DepartmentWorkspace.jsx` 15000ms, `RequestsBoard.jsx`/`TasksTab.jsx` main list/`ScheduleTab.jsx`/`MenuTab.jsx`/all Devices sub-tabs: **no poll at all**, manual refresh only). Options, cheapest first: **(a)** tighten/standardize polling intervals across the remaining screens to match `StaffDashboard`'s 3s-15s range — zero new infrastructure, matches what's already proven to work; **(b)** a Mongo change-stream-backed SSE endpoint for the specific `db.alerts`/`db.staff_tasks` collections, pushed to whichever admin screens are open — real new infrastructure, only worth it if (a) proves insufficient for a single front-desk-laptop pilot (it almost certainly won't be needed at pilot scale); **(c)** full WebSocket bus — not justified by anything in this audit.

## 18. EVENT HISTORY / REPLAY READINESS

**What's genuinely timestamped and reconstructable today:** `Alert.event_log[]` (`{at, field, from, to}`, `models.py:329`) is a real per-transition array — for resident-assistance events specifically, "what did this event look like at 10:17am" is answerable today by filtering `event_log` entries with `at <= "10:17"`. `db.conversations` (Aria transcripts) and `db.receipts` (created_at/acknowledged_at/completed_at) both carry real timestamps.

**What's missing:** `StaffTask` has NO equivalent transition array — only 5 named timestamp fields (`created_at`/`acknowledged_at`/`started_at`/`completed_at`/`last_re_requested_at`). A task that was assigned, unassigned, and reassigned leaves no trace of the intermediate state; only the current `assigned_to` value survives. `db.receipts`' `update_receipt_status()` (`receipts.py:83-111`) **mutates the most recent receipt in place** rather than appending a new one on each transition — so `db.receipts` for a given task shows "created" + whatever its LAST status update was, not the full sequence of created→acknowledged→in_progress→completed. **"What happened between 10:17 and 10:45" for a StaffTask cannot be fully reconstructed today** — only the two or three named timestamps that happen to fall in that window, not a complete state-transition log. `Alert`'s richer `event_log[]` does not have this gap. **If this matters for the replay goal, `StaffTask` would need the same append-only `event_log`-style field `Alert` already has — a small, additive model change, not a new subsystem.**

## 19. EXACT BOUNDARY BETWEEN SIMULATED AND REAL DATA (report-only proposal)

No `simulated: bool` field exists on any current model — verified by grep. The existing precedent for distinguishing generated-from-real data is entirely **naming convention**, not a schema flag: `seed_demo_community.py` uses `"Demo - "`-prefixed resident/staff names, `@demo.caoscare` emails, and a dedicated `3W01`-`3W10` room range that cannot collide with any real room (confirmed present: 10 `Demo -` residents, 5 `3W0x`-room tasks in the current DB). A month-long simulator following the same convention (a reserved room-number range or resident-name prefix, distinct from any real pilot resident) would be immediately, reliably filterable out of real metrics with a single `$not: /^Demo -/` / `room not in [reserved range]` query, without a schema change — though a proper `simulated: bool` (or `source: "simulation"` reusing the existing `TaskSource`/`EventSource` literal pattern) would be more robust and is a very small model addition if the naming-convention approach is judged too fragile at scale.

---

### What can be connected mostly with existing code
- Live Board's stale-count problem: fixable inside `ops_overview.py` alone (§9 Option B) — one function, no new architecture.
- Front-desk duplicate-request checking: reuse `resident_requests.py::create_resident_request()`'s existing dedup block (§12) — either loosen its `source` validation or extract the block into a shared helper; the matching/receipt/notification logic needs zero changes.
- Department workspace actionability: reuse `task_assignment.py::POST /tasks/{id}/assign` + `tasks.py`'s ack/start/complete endpoints inside `DepartmentWorkspaceDialog.jsx` — the exact pattern `MaintenanceWorkspace.jsx` already proves.
- Tasks screen edit/open: reuse `RequestDetailDialog.jsx`'s existing pattern (already calls `PATCH /tasks/{id}`) inside `TasksTab.jsx`.
- A future simulator's every domain action: `create_resident_request()`, `create_task()`, `task_assignment.py::assign`, `record_resident_activation()`, `transportation_engine.find_or_create_run()`, `menu_ingest.create_menu_upload()`, `schedule_ingest.create_schedule_items()`, `escalation.py::tick()` — all already exist and are exactly what real callers use.

### What actually requires new backend capability
- A `resident_id` query filter on `GET /alerts` (small, additive).
- `StaffTask` needs an append-only transition-history field equivalent to `Alert.event_log[]` if full replay/"what happened between X and Y" is a real requirement, not just nice-to-have.
- `db.receipts`' `update_receipt_status()` needs to append rather than mutate-in-place if receipts are meant to be a full audit trail (currently only the latest status per object survives).
- The `AlertStatus` enum needs `"escalated"` added, or `escalation.py::tick` needs to stop writing it — a real, live bug, not a design gap.
- A scheduler process (however small) to call `escalation.py::tick()` and, later, drive a simulator — genuinely does not exist in any form today.
- `simulated: bool` (or equivalent `source` value) on `StaffTask`/`Alert` if the naming-convention approach (§19) is judged insufficient.

### What is merely stale/test data
- 319/321 open `db.alerts` documents, ages 342-1010 hours, concentrated in rooms `401`/`test`/`TEST-*` from 2026-08-29→09-06 RF hardware testing — not a bug, historical test debris nothing has ever resolved.
- Local `db.menu_items`/`db.schedule_items` simply stop at 2026-09-13/09-05 respectively — a data-freshness gap with an existing, unused fix (the idempotent two-week seed scripts).
- 15 open transportation `StaffTask`s (11 counted as `needs_action`), all requested for dates on or before 2026-09-08 — the exact match for the user's reported "11 old unresolved transportation items."
- `TasksTab`'s "Today" label showing all 85 tasks — a display-label bug (the backend `day=` filter exists and is unused), not stale data per se.

### The 5 highest-leverage next implementation steps
1. `ops_overview.py`: exclude (don't just demote) alerts older than `STALE_HOURS` from the raw `assistance.active`/`open_total` counters — one file, directly fixes the headline "hundreds of active events" complaint. *(builds on `ops_overview.py::operations_overview`)*
2. `TasksTab.jsx`: pass `day=<today>` (or an explicit toggle) to `GET /tasks` — one line, fixes the misleading "Today" count. *(builds on the existing `day` param in `tasks.py::list_tasks`)*
3. Run the already-existing `seed_menu_two_weeks.py`/`seed_schedule_two_weeks.py` against this EliteDesk's local backend for the current date window — pure data op, zero code, fixes the empty Menu/Schedule tabs. *(builds on scripts already used successfully against production 2026-09-19)*
4. Loosen `create_resident_request`'s `source` allow-list (or extract its dedup block) so a front-desk-authenticated path can reuse the exact same duplicate-detection/receipt/notification logic. *(builds on `resident_requests.py::create_resident_request`, §12)*
5. Wire `DepartmentWorkspaceDialog.jsx` to the existing assign/acknowledge/start/complete endpoints, mirroring `MaintenanceWorkspace.jsx`. *(builds on `task_assignment.py` + `tasks.py`, already proven)*

### Month-long simulation recommendation (report-only — none of this is built)
- **Run continuously:** the escalation `tick()` on a real interval (e.g. every 60-120s, calling the existing `escalation.py::tick`), and a simple "time advances" loop reading `today_facility_date()`/`_facility_now()` — both already exist as functions, only the calling loop is new.
- **Random-within-bounds:** resident voice/front-desk requests, pendant help-presses (via `record_resident_activation()`, always pre-classified as `help_press` — never bypass `rf_semantics.classify_transmission`), transportation requests — Poisson-ish arrival, bounded rate per simulated hour.
- **Scheduled:** menu/schedule content generation via `create_menu_upload()`/`create_schedule_items()` (reuses this session's real inbound-email path or the dev-test path directly), daily/weekly recurring maintenance via `StaffTaskTemplate`'s existing `spawn-today`.
- **Deliberately exercise escalation:** a fixed fraction of simulated requests/alerts are intentionally never acknowledged by simulated staff within the SLA window, so `tick()` genuinely has something to escalate — this is the only way to prove the escalation path isn't just "correct in code," per the example timeline in the task's own directive (10:17→10:45).
- **Simulated staff close events:** by calling the exact real endpoints (`acknowledge`/`start`/`complete`/`assign`) as one of the few real `User` documents created via `POST /staff` per §16 — never a direct `db.staff_tasks.update_one()`.
- **Survive restart:** persist "what's the next scheduled simulated event and when" in its own small collection (or resume from `db.staff_tasks`/`db.alerts`' own `created_at` high-water-mark), rather than in-process memory only.
- **Prevent duplicate simulated events:** the SAME dedup mechanisms real traffic already uses (`create_resident_request`'s dedup, `record_resident_activation`'s open-incident coalescing) apply automatically to simulated calls for free, since the simulator would call the real functions, not bypass them.
- **Prevent contaminating real pilot metrics:** the `Demo -`/`3W0x`-style naming convention (§19) — reports/§9a's `ops_overview.py` and `reports.py` would need one additional filter clause to exclude the reserved simulation range, the same shape `seed_demo_community.py --wipe` already uses to safely scope its own cleanup.
- **Pause/resume/reset safely:** a single admin-only toggle (env var or a `db.simulation_state` doc with `running: bool`) the loop checks before firing its next event; "reset" = delete only documents matching the reserved simulation naming/range, exactly as `seed_demo_community.py --wipe` already does for its own demo data — never a blanket `db.staff_tasks.delete_many({})`.
- **Coexistence with real Room 214 hardware:** no change needed — Room 214's real resident (`res_81b72be1e8b5`/Helen Torres) and its real `rf_devices`/`rf_events`/`conversations` are keyed by real resident_id/room "214" already outside any reserved simulation range; a simulator using a disjoint room/resident range (per §19) coexists automatically with zero special-casing, the same way the existing `seed_demo_community.py`'s `3W0x` wing already coexists with Room 214 today (confirmed: this session's own count query shows Room 401's stale alerts and Room 214's real data are already two disjoint, non-interfering sets in the current database).
