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