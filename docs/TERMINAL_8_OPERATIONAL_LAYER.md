# Terminal 8 — Full Operational Connection + Aria Capability Build

Living build log for `commands`-relayed Terminal 8 (full operational integration: nursing, maintenance, kitchen, family, capability registry, conversation ledger, memory continuity, front-desk communication). Do not replace or erase prior entries — append dated sections as the build progresses.

This is explicitly **not** a single-session undertaking — the directive itself specifies 15 dependency-ordered build items, each with real acceptance tests. This log tracks genuine progress against that order, honestly, the same way `docs/ARIA_VOICE_FIRST.md` and the 13-part audit (`~/Desktop/FROM_CLAUDE.txt`) did for the voice work.

---

## 2026-08-09 — Item 1 (mapping) + items 2-4/5 (receipt foundation, request bus, nursing + maintenance Aria tools)

### Item 1 — mapping findings (the ones that drove architecture decisions below)
Read the backend route inventory (`backend/routes/*.py`, 30 files) and cross-checked the directive's assumptions against actual code:

- **`Alert`** (`backend/routes/alerts.py`, `models.py`) is already a real, working safety/emergency-call object: severity, status lifecycle (active→acknowledged→resolved), category, escalation_level, triggered_by, ack/resolve timestamps, AI-classified summary fields. This stays as-is — it's the emergency path, unchanged.
- **`StaffTask`** (`backend/routes/tasks.py`, 238 lines before this entry) is already a real, working, tested general work-item system: category, shift, assignment, status (pending/in_progress/completed/skipped), timestamps, templates for recurring work, a `spawn-today` materializer. This is the closest existing thing to what the directive calls a "resident request bus" — extended rather than duplicated (see below).
- **`Audit`** (`backend/routes/audit.py`, 157 lines) is a **CSV export layer** over Alert/Task/Page/Medication collections — it does not create records or provide a generic receipt mechanism. Confirmed again this entry (matches the earlier 13-part audit's finding).
- **`escalation.py`** is an alert-escalation SMS-timer/rule system, not a resident-request or nursing-communication object — a plausible-sounding name that turned out to be something else entirely; worth recording so a future agent doesn't assume it's reusable for nursing requests.
- **`family_portal.py`** is a thin, read-only, token-based family summary view (2 routes) — not a structured contact/relationship model. `FamilyContact` (in `models.py`) exists with `relationship` as a free-text string, not a typed enum (daughter/son/spouse/guardian/emergency contact) — item 10's work is not started.
- **No menu/kitchen/meal/dietary domain model exists anywhere** (`grep` confirmed) — item 7/8 genuinely starts from zero.
- **No nursing/clinical request object distinct from Alert exists** — item 4 genuinely starts from zero, now addressed below.

### Item 2 — shared operational receipt foundation
Per "one source of truth, reuse existing models" — did **not** build a second logging database. Added:
- `Receipt` model (`backend/models.py`) — generic record that **points at** a domain object (`related_object_type`/`related_object_id`) rather than duplicating its fields. Fields match the directive's list: source, resident_id, room/zone, conversation_session_id, requested_by, assigned_role/user, status lifecycle, timestamps, result/failure_reason, follow_up_required.
- `backend/routes/receipts.py` (new, 128 lines) — `create_receipt()`/`update_receipt_status()` as **importable Python functions** other route modules call directly (not just HTTP endpoints), plus `GET /api/receipts` (admin, filterable) and `GET /api/receipts/{id}` for reading. This is the pattern other domains (maintenance, kitchen, family, when built) should call into rather than each inventing their own event log.

### Item 3 — resident request bus + role-based visibility
Extended `StaffTask`/`TaskCategory` rather than building a parallel object:
- New categories: `nursing`, `maintenance`, `kitchen`, `front_desk`, `family`, `complaint` (alongside the existing `laundry`/`meds`/`meal`/`rounds`/`bathing`/`housekeeping`/etc.).
- New fields: `priority`, `source` (staff/aria_voice/kiosk_button/family/system), `visibility_role` (which department's queue this belongs in), `resident_words` (verbatim quote when resident-originated), `conversation_session_id`, `acknowledged_by`/`acknowledged_at`.
- New public endpoint `POST /api/tasks/resident-request` — deliberately narrower than the admin-only `POST /api/tasks`: fixed category allowlist, server-derives `visibility_role` from category (never trusts a caller-supplied role), no arbitrary assignment. This is what Aria/the kiosk call — same public trust model as the existing `/alerts` and `/devices/public/...` endpoints already used by the resident Realtime tools.
- New public endpoint `GET /api/tasks/resident-request/status` — lets a resident/Aria ask "did anyone see my request" and get a **real** answer (found/not-found, actual status, acknowledged bool, assignee name) instead of a guess.
- **Role-based visibility, backend-enforced**: added an optional `department` field to `User` (nullable — `nursing`/`maintenance`/`kitchen`/`housekeeping`/`administration`). `GET /api/tasks` now filters by the requesting staff user's department when role is `staff` (sees their department's items + `all_staff`-visibility items); `mine_only` still works as before; admin/owner continue to see everything. **Not verified against a real multi-department staff account** — only the one owner account exists on this host. This is real, wired code, not a stub, but it has exactly one account to have ever exercised it (the admin/owner path, which bypasses the filter by design).

### Items 4 + 5 — nursing + maintenance capability for Aria (built together — the backend is category-agnostic)
Added two Realtime tools to the resident-facing tool catalog (`backend/routes/realtime_tools.py` — see file-split note below):
- **`request_staff_help`** — category (nursing/maintenance/kitchen/front_desk/housekeeping/complaint), summary, priority. Calls `POST /tasks/resident-request`. Tool description explicitly tells the model: after calling, say the request was *created and sent*, not that someone is already on the way, unless `check_request_status` confirms it.
- **`check_request_status`** — optional category filter. Calls `GET /tasks/resident-request/status`. Tool description explicitly forbids claiming acknowledgment/completion the tool result doesn't actually report.
- Wired dispatch in `frontend/src/lib/useRealtimeVoice.js`'s `executeTool()` for both.
- This directly implements the directive's "truthful distinctions: created / sent-routed / acknowledged / assigned / resolved" requirement at the tool-description level, matching the exact truthfulness pattern already proven working live (Michael's test: Aria said she'd *remember* the nursing need rather than claiming she'd contacted nursing — this makes that same honesty possible for a *real* nursing/maintenance request too, not just a memory note).

### File-size cleanup (done proactively per explicit instruction mid-session: "files should not be monoliths, 400 lines max unless needed")
`backend/routes/realtime.py` had already been flagged as debt (826→940→1036 lines across earlier entries) and was about to grow further from the two new tool schemas. Split it:
- `backend/routes/realtime_tools.py` (new, 342 lines) — `_build_tools()`, the full resident tool-schema catalog (now 13 tools).
- `backend/routes/realtime_self_knowledge.py` (new, 110 lines) — `_system_self_knowledge()`, the "about yourself" platform-identity block.
- `backend/routes/realtime.py`: **1,095 → 662 lines.** Still over the 400 cap — not fully resolved, `_build_companion_instructions`/`_build_aria_instructions`/the actual route handlers are still one file — but meaningfully smaller and nothing new was added to it this entry.

### What was verified
- Full lifecycle tested end-to-end via real API calls (not simulated): created a resident maintenance request through the public endpoint → confirmed it appears correctly in the admin task list with the right category/visibility_role/source → confirmed a matching receipt exists → completed the task via the authenticated endpoint → confirmed the receipt's status/result/completed_at updated to match. Test data cleaned from the database afterward.
- Caught and fixed a real bug during this testing: `update_receipt_status()` initially used `update_one(..., sort=...)`, which Motor/PyMongo doesn't support on that method (only `find_one_and_update` accepts `sort`) — would have thrown a 500 on every single task completion/skip in production. Found via the actual test failing, not code review.
- Confirmed the invalid-category safety check rejects out-of-scope categories (e.g. `paperwork`) with `400`, not silently accepting them.
- Confirmed both new tools appear correctly in a freshly-minted resident Realtime session after the file split (13 tools total, `request_staff_help` and `check_request_status` present) — the split didn't silently break tool delivery.
- Backend restarted cleanly (syntax-checked first) each time; exactly one process confirmed listening on `:8000` throughout.
- Frontend hot-compiled with no new errors (same one pre-existing unrelated warning as every entry this session).
- **Not yet verified**: an actual live conversation where a resident/Michael asks Aria to raise a nursing or maintenance request and hears the correct truthful response. The backend/tool-wiring is proven at the API level; the live voice acceptance test (directive's own Acceptance Test A and B) has not been run.

### What is NOT done (honest, matches the directive's own "do not claim complete" instruction)
Items 6-15 of the specified build order: conversation viewer/ledger admin UI (item 6, though the underlying `db.aria_conversations`/`db.conversations` data already exists from earlier work), capability registry properly connecting Aria's tool routing to the existing `db.aria_capabilities` maturity states (item 7 — Aria's tools are still just prompt-declared, not gated by verified_control status), the entire menu/kitchen system including email ingestion (item 8-9), meal operations (item 10... directive's item 8), open loops/follow-up tracking (item 16 in the original numbering), memory continuity/reconciliation (item 15/6 in original numbering — still 0 records, per the 13-part audit), queryable action/device history (item 14), staff tablet UX pass (item 14 in the 15-step order), family/contact structured relationships (item 10), and the front-desk communication service (added as a new requirement after this entry started — not yet designed or built).

### Next safe step
Either continue down the build order (item 6: wire a conversation-viewer admin UI reusing the already-built `aria_conversations`/`conversation-threads` endpoints from earlier today, extended to also list resident conversations) — or run Acceptance Tests A/B live first to prove items 3-5 actually work end-to-end for a real person before building further on top of them. Recommend the latter: a live test now is cheap and would catch any remaining issue before more is built on this foundation.

### File-size correction (2026-08-09, follow-up)
Michael caught that the earlier `realtime.py` split left it at 662 lines — still over the 400-line cap, not fully done. Corrected as a surgical continuation, not a broader refactor: extracted `_build_companion_instructions` (315 lines, the largest remaining chunk) into `realtime_companion_prompt.py`, and `_facility_now()`/`FACILITY_LABEL`/`FACILITY_TZ` into a small shared `realtime_facility.py` (needed by both `realtime.py` and the new companion-prompt file, to avoid a circular import). `realtime.py`: 662 → 314 lines. All five `realtime_*.py` files now under the cap (314/342/328/110/41). Re-ran the exact same regression checks as the first split (both session endpoints' tools/instructions, and a real `aiortc`-generated SDP through `/negotiate`) — nothing broke.

## 2026-08-09 (continued) — Item 6: conversation viewer (mostly already existed)

### Finding, not building from scratch
Before building anything, checked whether a resident conversation viewer already existed. **It did** — `frontend/src/pages/MemoryDialog.jsx` (pre-existing, predates this session) already has a working "Conversation" tab, fetching `GET /api/memory/conversation/{resident_id}` (also pre-existing), reachable from Admin → Residents tab → "Memory" button on any resident row. This satisfies most of item 6's "Michael must be able to go into CAOSCare and read the conversations that occurred" requirement already — confirmed by inspection first, exactly the "do not assume documentation equals implementation, but also do not duplicate what's real" balance the directive itself asks for.

### The actual gap: today's new request/receipt system wasn't reachable from this existing resident view
Item 6 also asks for "Requests/Tasks" and "Events/Receipts" to be reachable from the resident admin experience. Closed that specific gap:
- `GET /api/tasks` gained a `resident_id` filter (didn't exist before - the endpoint only supported `mine_only`/`status`/`day`/`category`/`visibility_role`).
- `MemoryDialog.jsx` gained a third tab, "Requests," showing that resident's staff requests (category, status, verbatim resident words when available, source, assignee) - reuses the exact same `StaffTask` data the nursing/maintenance Aria tools write to, no new storage.

### What was verified
No real residents exist on this host (`GET /api/residents` returns `[]`) - a genuine environmental constraint on testing anything resident-scoped. Created one temporary test resident to actually prove this live rather than trust it un-tested:
- Created a real nursing request for that resident via `POST /tasks/resident-request`.
- Created a real conversation turn via `POST /memory/realtime-turn`.
- Confirmed `GET /memory/conversation/{resident_id}` (the pre-existing endpoint the Conversation tab uses) returns it correctly.
- Confirmed `GET /tasks?resident_id={id}` (the new filter) returns the nursing request correctly, with `resident_name` resolved.
- Deleted the test resident, task, receipt, conversation turns, and auth token afterward - no test data left in the database.
- Frontend hot-compiled with no new errors beyond one new instance of the same pre-existing `exhaustive-deps` lint pattern already tolerated elsewhere in this codebase (`fetchAll` not in a `useEffect` dependency array - unchanged behavior, not a new issue class).

### Still not done for item 6
No dedicated "thread" grouping (the Conversation tab shows one flat chronological list across all sessions, not grouped by `session_id` the way the Aria operator conversation viewer built earlier today does) - functional for reading what happened, not as structured. Aria's own operator conversations remain viewable only from `/aria` itself, not from any admin surface (arguably correct, per the directive's own "Operator Aria conversations remain separate from resident records"). "Clinical," "Family," "Devices" tabs in a unified resident profile view are not built - Family/Devices/Clinical data exists elsewhere in the admin UI (`FamilyTab`, `DevicesTab`, `ClinicianTab`) but aren't cross-linked from this same resident-detail dialog.

---

## 2026-08-10 — Product-direction handoff: the operator frame, handset, room mailbox, calendar-backed transportation

**No code changed in this entry.** Michael planned the next phase of Terminal 8 (items 8-9 plus two new lanes) in a separate browser-based Claude session, then handed a written summary to this session. What follows is that handoff, reconciled against this file's own record — it supersedes the same-day entry immediately above where the two disagree (transportation's lifecycle and the calendar decision, specifically — the first version of this entry, written before the formal handoff arrived, underspecified both). **Direction only, nothing here is implemented.**

### 0. The frame: Aria is the operator, CAOS is the switchboard
The resident mental model is the old telephone operator/411: pick up, say what you need, it gets routed and handled. No departments, no menus, no app to learn — the thing every resident already knows how to do. This reframes the pitch too: not "an AI voice system" (which a no-AI-zone corporation has to evaluate) but "we restored the operator" — a familiar, human-feeling front desk. The AI stays invisible on both the resident's and corporate's side.

### 1. Physical interface decision: handset-first, not built now
A real telephone handset (speaker + mic + hook switch wired into the room node) as the eventual resident front end — lift to start a session, hang up to end it, reusing the *existing* voice-first Realtime flow behind it (new front end, not a new conversational system). Rationale: 60-70 years of muscle memory beats any new UI for this population. Dial-shortcut complexity explicitly deferred — do not build that first. **Direction only** — needs a chosen EliteDesk-connected test room before any prototyping starts, which hasn't happened. The kiosk/browser UI remains the dev/acceptance-test surface, not the resident product, unchanged from the prior Terminal 8 handoff.

### 2. The per-room answering-machine mailbox
Each room has its own mailbox. Staff (nurse, maintenance, PT, front desk) leave a message; on next pickup, Aria reads it back — "Hey, how's it going? You've got three messages." This is **inbound** (staff → resident), a different direction from the request/receipt bus built today (resident → staff), and needs its own data model: no schema, route, or tool exists yet. Same truth discipline as everything else in this system: real count, real read/unread state, attributed content ("the nurse says..."), never softened or invented.

Message timing truth: because the system will know real nurse on-floor hours, a message can carry a real time ("the nurse will be on the floor at 2") instead of a vague "she's on the way" — this replaces the "need an urgent-flag hack" instinct with just reading the real schedule. This is a **staff-side** schedule (who's on, when) — a different source from lane 1's resident-facing activities schedule below, same provenance-stamped shape.

### 3. Email/calendar as the compliance strategy, restated as a hard rule
Corporate only ever sees an inbox and an Outlook calendar being used the way staff already use them — nothing new appears on their side. All intelligence lives on Michael's own node. Two hard rules this reinforces (not new, but worth stating explicitly here):
- **Email/calendar are delivery and data adapters, never the source of truth.** CAOSCare owns request, status, thread, receipt, assignment, acknowledgment, history — never bind the domain model to email or Outlook shapes.
- **No AI surface may become visible on corporate-owned infrastructure.** The instant that happens, corporate has a reason to say no. This is what preserves the workaround Michael has been running for months.

### 4. Three inbound lanes, one adapter pattern, build order confirmed
1. **Schedule/activities lane (ship first)** — read-only: "AC turns off at this time," "activity's at 2." Same shape as the menu (date, time, item, approved-state, provenance) but doesn't need email ingestion to start — staff-entered records are enough to prove the "structured source → honest answer → provenance" read pattern end to end before tackling parsing complexity. No request, no receipt, no routing.
2. **Menu lane** — same read pattern plus a **non-negotiable approval gate**: a hallucinated "we're having X" is a real health-adjacent failure for a resident with dietary restrictions, not just an annoyance. Menu answers must be provenance-stamped to an approved upload, or Aria says "let me check." Nothing new decided here beyond reconfirming the gate isn't optional.
3. **Transportation lane** — see §5, corrected below; it's not a plain request-and-forget lane.

### 5. Transportation — corrected (this is the substantive change from the earlier same-day entry)
The first pass at this entry recorded transportation as pure fire-and-forget off Michael's own words in the moment ("it's all gonna be on request base"). The formal handoff clarifies it's **request-based with revise/cancel**, backed by a real published Outlook calendar:
- **Availability source of truth**: a published Outlook calendar CAOSCare reads to check whether a transportation slot exists.
- **Calendar ownership, and why write access is safe here**: Michael confirmed this calendar is his own tenant/provisioned calendar, not corporate Outlook — designed intentionally that way. Because it's not corporate infrastructure, CAOSCare **may write to it** to actually hold a slot. Had this been corporate Outlook, only read/subscribe would be safe and a human would own booking — that distinction matters and should hold for any *other* calendar this pattern gets reused against later.
- **Revise/cancel is just the same read/request loop re-run**: read current availability → request the change → read back confirmation. Not a separate heavy lifecycle — the loop is the lifecycle.
- **Shared field**: `requested_for`/preferred-time ("Thursday," "after lunch") — build once, shared with nursing's "talk to my nurse tomorrow" case. Don't flatten "Thursday" into "now."
- **Capability-state discipline applied to the calendar** (the same verified_read/verified_control distinction named for devices in item 7 of the prior entry, now applied to scheduling): an open slot is `verified_read` — Aria may say "there's a slot Friday at 2, I've put in your request." A slot is `verified_control` only once the calendar write succeeds and a receipt confirms it — only then may Aria say "you're booked." Never report a booking before both exist.
- **Concurrency**: two residents (or CAOS and a human) requesting the same last slot needs a slot-lock/acceptance step before either side reports it as confirmed. Mechanics not yet decided — flagged as open, not designed here.

### 6. Bidirectional loop: extend, don't fork
Staff replies into a resident's mailbox (§2) should live in the same governed request/thread/receipt structure already built today, with email/calendar as transports only. Explicit instruction: prefer extending `StaffTask`/the request bus into a canonical resident communication thread over forking a new primitive — same one-source-of-truth discipline already applied everywhere else in Terminal 8.

### Correction to the handoff document itself, made here rather than silently
The handoff's own "immediate next steps" lists closing out the `sessionIdRef` browser bug with a live mic test as still outstanding ("until that mic test passes, that fix is 'reported,' not 'real'"). **That's already done** — Michael ran the real live test himself earlier in this same session (the faucet-leak conversation) and reported a successful outcome directly, which is recorded in the entry two above this one. The browser-based session that drafted this handoff didn't have that context. Not correcting it there would leave a stale "still open" item in the permanent record contradicting this file's own more current entry — flagging it here instead of re-litigating it as unfinished.

### What's still genuinely open (not decided anywhere in this conversation)
- How inbound email actually reaches this node for lanes 2/3 — real mailbox to poll via IMAP, or build the adapter against sample data first and wire up the real mailbox later. Asked directly, not yet answered. Does not block lane 1.
- Slot-lock/acceptance mechanics for concurrent calendar writes (§5).
- Dedupe/escalation policy for repeated requests generally, preserving the clinical-vs-convenience distinction the maintenance re-request feature already established today.
- Front-desk room-to-desk audio/calling architecture.
- Family authorization/visibility specifics for the mailbox.
- Which physical room/hardware the handset gets rigged and tested in first.
- No schema/route/tool exists yet for any of: the schedule/activities source, the menu source (draft/approve states), the room mailbox, the staff-hours source, or the transportation calendar integration. All new data models — none invented here without Michael's input, per this project's standing "do not invent" rule.

### Recommended next safe step
Build lane 1 (schedule/activities) first, staff-entered, no email/calendar dependency — proves the structured-source → honest-answer → provenance pattern live through the actual resident voice path before either the menu approval gate or the transportation calendar read/write loop raise the stakes. Get Michael's answer on the inbound-email mechanism in parallel, since it gates lanes 2-3 but not lane 1.

---

## 2026-08-10 (same day, continued) — Lane 1 (schedule/activities) built and smoke-tested

Michael: "we continue building until i can see the emails come in" — i.e. keep building everything that doesn't actually require a real inbound mailbox, and stop only when the next step genuinely needs one. Lane 1 needs no email at all (staff-entered, per the plan above), so it was built in full.

### What was built
- `backend/models.py`: `ScheduleItem`/`ScheduleItemCreate`/`ScheduleItemUpdate`. Fields: `date` (facility-local YYYY-MM-DD), `time_label` (free text, staff-friendly), `title`, `description`, `category` (`activity` | `facility_note` | `staff_hours`), `source` (`staff_entry` for now, ready for an email/calendar adapter to feed the same model later without Aria or residents needing to know the difference), `created_by`, timestamps.
- `backend/routes/schedule.py` (new, 97 lines): admin CRUD (`GET/POST /schedule`, `PATCH`/`DELETE /schedule/{id}`, staff/admin/owner only) plus `GET /schedule/public/today` — no auth, same public trust model as the other resident-facing endpoints Aria calls live, returns only approved-by-definition staff-entered items (no draft/approve gate for this lane — deliberately, per the plan's own "lowest-risk lane, no clinical/dietary edge" reasoning that's specific to menus). `_today_facility()` resolves "today" in the facility's own timezone (reuses `_facility_now()`/`FACILITY_TZ` from `realtime_facility.py`) so a UTC day-rollover can't make an item entered "for today" read as tomorrow's.
- `backend/server.py`: registered the router.
- `backend/routes/realtime_tools.py`: new `get_todays_schedule` tool in the resident catalog (14 tools total now) — explicit in the tool description: answer only from what the call returns, say honestly if nothing's listed, never invent an activity or time.
- `frontend/src/lib/useRealtimeVoice.js`: dispatch for `get_todays_schedule` — calls the public endpoint, reads back "today: 2:00 PM: Bingo in the common room; ..." or "nothing is listed on today's schedule yet" if empty.
- `frontend/src/pages/ScheduleTab.jsx` (new, 135 lines) + wired into `Admin.jsx` as a new "Schedule" tab — date picker, add/delete, same visual/interaction pattern as the existing Tasks tab so staff have an actual way to enter this without hitting the API by hand.

### What was verified
Restarted the backend clean (no import errors from the new router). Frontend hot-compiled with no new errors (same pre-existing `exhaustive-deps` warning pattern already tolerated elsewhere, now also flagged once in `Admin.jsx` for the same reason `ScheduleTab.jsx`'s own date-dependent refetch triggers it — not a new issue class). Full lifecycle tested against the live running backend, not simulated: minted a real JWT for the owner account, created a real schedule item via the authenticated endpoint, confirmed it appears in the admin list, confirmed the exact public endpoint the Aria tool calls (`GET /schedule/public/today`) returns it with only the resident-safe fields (no `created_by`/`schedule_id`/timestamps leaked), deleted it, confirmed the public endpoint goes back to empty. Separately minted a fresh resident Realtime session and confirmed `get_todays_schedule` is present among 14 tools — the split/registration didn't silently break tool delivery.

### Not yet verified
A real live voice conversation asking "what's happening today" — this entry proves the mechanism the same way the maintenance-request fix's `aiortc` reproduction did, which is strong but is not itself the resident-facing voice test this project's own standard requires before calling something done. Also: no schedule items exist in the database right now (test data was cleaned up), so the honest "nothing is listed for today yet" path is what a live test would currently hit until Michael adds a real one via the new Schedule tab.

### Next safe step
Michael adds a real schedule item via Admin → Schedule, then live-tests "what's happening today" (or "what's on the schedule") at the kiosk. If that works, move to lane 2 (menu) — same read pattern plus the non-negotiable approval gate — which, like this lane, can also start staff-entered and doesn't have to wait on the inbound-email answer either.

---

## 2026-08-10 (continued) — Lane 2 (menu) built: staff CRUD + approval gate + email-adapter boundary, smoke-tested including the correction/history scenario

Michael: "we continue building until i can see the emails come in" — menu lane needed no real mailbox either (staff-entered + a dev-test ingestion path that exercises the exact same parse→draft→approve pipeline a real email adapter will later feed), so it was built in full per two directives: the original menu-lane plan, then a follow-up specifically scoping the email-ingestion adapter.

### What was built
- `backend/models.py`: `MenuItem`/`MenuItemCreate`/`MenuItemUpdate` (`date`, `meal_period`, `item_name`, `description`, `availability`, `status`: draft/approved/**superseded**, `source`, `upload_id`, `created_by`/`approved_by`/`approved_at`). `MenuUpload`/ingestion model: one record per "an email arrived" event — `source`, `source_ref`, preserved `raw_text`, `service_date`, `parse_status` (parsed/needs_review), `parse_notes`, batch `status`, `item_ids`.
- `backend/routes/menu.py` (117 lines): admin CRUD, `POST /menu/{id}/approve` (editing an approved item drops it back to draft — an edit is unreviewed content again), `GET /menu/public/today` — **hard-filters `status=approved`**, the actual enforcement point of the gate. No auth, same trust model as the other resident-facing reads.
- `backend/routes/menu_ingest.py` (new, 162 lines): `POST /menu/ingest/dev-test` simulates an inbound email (no real mailbox exists yet) — takes `{service_date, raw_text, source_ref}`, runs a deliberately simple deterministic parser (regex section headers for Breakfast/Lunch/Dinner/Supper, splits items on newline/comma, `supper` normalized to `dinner`), creates draft `MenuItem`s + one `MenuUpload`. Flags `needs_review` with a specific reason when a section is missing rather than guessing. `POST /menu/uploads/{id}/approve` approves the whole batch in one action.
- **Daily-replacement/history rule** (this is what makes a corrected menu actually replace the old one instead of showing both): approving an upload supersedes any other previously-approved `MenuItem`s for the same `(date, meal_period)` — sets them to `status=superseded`, excluded from the public read but retained in the database for history/provenance. Scoped to whole-upload batches only; a single manual item edit does not supersede its siblings (that's fixing one dish, not replacing the day's whole meal).
- `backend/routes/realtime_tools.py`: `get_menu` tool now accepts optional `date` (model computes "tomorrow" itself from the facility date/time already in its prompt) alongside `meal_period`; description explicitly maps `supper`/`evening meal`→dinner, `morning meal`→breakfast, `noon meal`→lunch so residents never have to use database terminology.
- `frontend/src/lib/useRealtimeVoice.js`: `get_menu` dispatch passes `date` through when the model supplies one.
- `frontend/src/pages/MenuTab.jsx` (+ new `MenuUploadsPanel`, 233 lines total): draft/approved badges, per-item Approve button, plus a "Ingest test email" dialog and an uploads list showing parse status/warnings/approval state — the smallest sensible staff surface, reusing the existing Admin tab pattern rather than a separate kitchen app.

### What was verified — full acceptance test from the directive, against the live backend
1. Ingested a realistic one-day dev-test email with all three meals → parsed cleanly, 11 draft items created, one `MenuUpload`.
2. Confirmed the draft items are **invisible** to `GET /menu/public/today` (the gate holds) before approval.
3. Approved the upload; confirmed all three meal periods now return the correct real items via the exact endpoint the Aria tool calls (breakfast: 4 items, lunch: 3, dinner: 4).
4. Sent a second, corrected dinner-only email ("Roast turkey, stuffing, cranberry sauce" replacing the original "Baked chicken..."), approved it, and confirmed the public dinner read shows **only** the correction — the old dinner items moved to `superseded`, breakfast/lunch (untouched) remained live and unaffected. Admin view confirmed both states exist (10 approved, 4 superseded) — full history preserved, nothing erased.
5. All test data (14 menu items, 2 uploads) deleted afterward. Frontend hot-compiled clean throughout (same pre-existing lint warnings only).

### Honest status against the directive's own categories
- **DONE**: structured menu model with approval gate; dev-test ingestion adapter with a real (if simple) parser; daily-replacement/supersession with preserved history; `get_menu` tool with date + natural-language meal synonyms; staff view (drafts, parse warnings, approval state, source).
- **PARTIAL**: attachment parsing (PDF/image/CSV) explicitly not built, per the directive's own "don't turn this into a giant document-processing project" — plain-text body only.
- **BLOCKED**: real inbound email reception. No mailbox/IMAP/webhook is connected — this was already the open item from the earlier product-direction handoff and remains unanswered. The dev-test endpoint is a faithful stand-in for the parse/approve/publish pipeline, but nothing here claims real email is live, per explicit instruction not to invent credentials or claim ingestion is live when it isn't.
- **NOT YET TESTED**: the actual resident-facing voice path ("what's for supper?" spoken into a real kiosk mic). Verified at the same protocol level as every other lane this session — real backend, real data, real endpoint the tool calls — but not a live human voice test, which remains this project's own bar for "done."

### Next safe step
Real live voice test of "what's for breakfast/lunch/supper" once Michael's added a real day's menu via Admin → Menu (or the dev-test ingest button). Separately, still waiting on the inbound-email-mechanism answer to unblock real ingestion for this lane and transportation's request notifications.

---

## 2026-08-10 (continued) — Lane 3 (transportation) pilot: full request/change/cancel/complete lifecycle, real concurrency proof, daily operations report

Per the transportation pilot directive: two-week synthetic availability, five obviously-fake TEST rooms, realistic request activity, and a daily report that reconciles everything. This is TEST/DEVELOPMENT DATA, left in the database on purpose (not cleaned up like the earlier verification smoke tests) so the report has something real to show — every resident/room is prefixed "TEST".

### What was built
- `backend/models.py`: `TransportSlot` (availability ledger - `date`, `start_time`, `end_time`, `capacity`, `booked_count`, separate from the request itself per the directive's "availability/request/booking stay separate concerns" rule). `StaffTask` gained two shared fields designed for reuse beyond transportation: `requested_for_date`/`requested_for_time_label` (nursing's "talk to my nurse tomorrow" can use the same two fields later, per explicit instruction not to invent per-department time semantics) and `transport_slot_id`. Added `"transportation"` to `StaffDepartment`, `TaskCategory`, `TaskVisibilityRole`.
- `backend/routes/notifications.py`: promoted `_notify_department` (previously private to `resident_requests.py`) to a shared `notify_department()` — now the one notification path for staff requests, transportation, and (implicitly) any future lane, instead of duplicating it a third time.
- `backend/routes/transportation.py` (389 lines): slot seeding (`POST /slots/seed-two-weeks`, idempotent, 14 days × 9 hourly slots 8am-4pm, capacity 1), availability read (admin + public), and the request lifecycle - `POST /request` (dedup/re-request on same resident+date, atomic slot reservation, receipt, department notification), `/request/{id}/change` and `/change-mine` (resolves by resident/room/session context since Aria has no task_id to work with), `/request/{id}/cancel` + `/cancel-mine`, `/request/{id}/complete` (staff-authenticated - a ride actually happening is a real-world fact only staff can confirm), `/request/status`.
- **The actual concurrency guard**: `_reserve_slot()` uses `find_one_and_update` with `$expr: {"$lt": ["$booked_count", "$capacity"]}` inside the atomic filter, so the increment only applies when a seat is genuinely still open at the moment of the operation - not a read-then-write race. Verified under real concurrent load, not just sequential ordering (see below).
- `backend/routes/transportation_report.py` (111 lines): `GET /transportation/report?date=` - inbound (requests received that day), outbound/actions (every receipt filed that day, labeled), current state (upcoming/waiting/follow-ups-required), summary (counts + slot utilization). Pure aggregation over `StaffTask`/`Receipt`/`TransportSlot` - never derived from email/inbox state, per the directive.
- Aria tool wiring: `check_transportation_availability`, `request_transportation`, `check_transportation_status`, `change_transportation_request`, `cancel_transportation_request` - `realtime_tools.py` had grown to 481 lines adding these plus the earlier schedule/menu tools, so the whole operational-bus tool set (staff requests, transportation, schedule, menu - 11 tools) was split into `realtime_tools_operations.py` to get both files back under the 400-line cap (287/209).
- `frontend/src/lib/useRealtimeVoice.js` had grown to 652 lines adding the transportation dispatch on top of pre-existing debt flagged earlier this session - rather than deferring again (the directive's own rule 12 explicitly forbids enlarging an oversized file when a modular home exists), extracted **all** operational-bus tool dispatch (staff requests, transportation, schedule, menu - the same 9 client-side handlers) into a new `frontend/src/lib/realtimeOperationsTools.js` (169 lines), called from `executeTool` as a first-check delegate. `useRealtimeVoice.js` is back to 510 lines - still over cap (pre-existing WebRTC/session-management debt untouched, not a new violation), documented here rather than silently left unmentioned.
- `backend/scripts/seed_transportation_pilot.py`: the pilot script itself, runnable standalone (`python3 scripts/seed_transportation_pilot.py`) against the live backend.
- `frontend/src/pages/TransportationTab.jsx` (112 lines) - new Admin tab: date picker, summary tiles, inbound/outbound/current-state sections, a "Seed 2-week schedule" button. Smallest sensible surface, same pattern as Schedule/Menu tabs.

### Real bug found and fixed during this work
The report's "today" filter initially compared `created_at` (stored in UTC) against a raw string prefix of the facility-local date - the **exact same class of UTC-vs-facility-timezone bug already fixed once elsewhere this session** (Aria's day/night greeting). It silently returned zero inbound/outbound results despite real data existing, because the facility's calendar day (`2026-08-09`) lags UTC (`2026-08-10T03:38...`) at this hour. Fixed by converting `created_at` to the facility's own timezone before comparing (`_local_date()` in `transportation_report.py`), not by adjusting the stored data. Caught by actually reading the report's output and noticing zero counts against known real activity - not by code review.

### What was verified — against the live running backend, not a reproduction
Ran `seed_transportation_pilot.py` for real: created 5 TEST residents/rooms, seeded 126 real availability slots, then exercised:
- **A**: TEST Room 101 requests a pharmacy ride tomorrow at 10 → booked at 10:00-11:00. PASS.
- **B (concurrency)**: TEST Rooms 102 and 103 fired **simultaneously** (`asyncio.gather`, not sequential) at the exact same slot (day+3, 14:00, capacity 1). Exactly one came back `booked=true`; the other `booked=false` with a `transportation_no_slot` receipt filed. This is a genuine proof the atomic guard holds under real concurrent access, not merely that a naive "check-then-write" happens not to race in practice. PASS.
- **C**: Room 101 "change mine to 2 PM" → old 10:00 slot released, new 14:00 slot booked. PASS.
- **D**: Room 101 "cancel my ride" → status `skipped`, slot released. PASS.
- Additional synthetic activity: two more bookings (grocery, bank), a third resident (103) deliberately targeting an already-booked slot (hair appointment, room 202) → correctly declined no-slot, then asked again for the same day → correctly detected as a re-request (not a duplicate task), bumping `re_request_count`. One booked ride (grocery) marked completed by staff.
- **E/F (daily report)**: after the timezone fix, the report for today shows 7 inbound requests, 13 outbound actions, and every summary count cross-checks exactly against what the scenarios produced (5 booked, 1 completed, 1 cancelled, 2 waiting/unresolved, 1 flagged for follow-up, 2 declined-no-slot) - nothing lost, nothing double-counted.
- Confirmed all 5 new Aria tools appear in a freshly-minted resident Realtime session (20 tools total). Frontend and backend both restart/recompile clean throughout.

### Honest status against the directive's own categories
- **DONE**: two-week synthetic schedule, 5 TEST rooms, full request/change/cancel/complete lifecycle, real (not simulated) concurrency guard proven under actual concurrent load, re-request/dedup detection reusing the same pattern built for maintenance/nursing, daily operations report reconciling inbound/outbound/current-state/summary, department email notification on every transportation event (reusing the existing `notify_department`), Aria tool wiring for all five capabilities with `verified_read`/`verified_control` language enforced in the tool descriptions.
- **PARTIAL**: the admin report UI is intentionally minimal (numbers + lists, no filtering/export yet) - matches "smallest sensible place," not a finished ops dashboard.
- **BLOCKED**: real Outlook calendar integration. Availability is an **internal CAOSCare schedule** (`TransportSlot`, `source: "internal_schedule"`), not yet synced with the Michael-controlled calendar the product-direction handoff describes. This pilot proves the internal request/booking/report loop works correctly; calendar sync is a separate, not-yet-built adapter, exactly as the directive itself anticipated as the likely outcome ("if not yet implemented/verified... mark PARTIAL/BLOCKED"). Nothing here claims real calendar sync exists.
- **NOT YET TESTED**: the actual resident-facing voice path. Every scenario above was driven directly against the same public endpoints the Aria tools call (not a mock), which is strong evidence the mechanism is sound, but per this project's own standard a live human voice test is still the only complete confirmation, and none has been run for transportation yet.

### Next safe step
Michael reviews the seeded pilot data via Admin → Transportation (and Tasks, for the underlying requests) to see whether the report actually surfaces something useful, then live-tests a real transportation request by voice ("I need a ride to the pharmacy tomorrow"). Separately: decide on the real Outlook calendar sync adapter now that the internal loop is proven, and continue waiting on the inbound-email-mechanism answer that still gates real menu/transportation email ingestion.