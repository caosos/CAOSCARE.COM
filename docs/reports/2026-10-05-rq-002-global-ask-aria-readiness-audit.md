# RQ-002 Global Ask Aria — readiness audit (read-only)

**Result: WAITING.** The exact blockers are in §3.
**Auditor:** Agent Six (Claude Code, Opus 5.5), Round 5. This was a read-only inspection: no production code was edited and nothing was probed on the live site.
**Inspected ref:** `integration/2026-09-27` @ `a42973d49672e78814a9ff5503aa1c189128c6d1`, read through `git show` / `git grep` on the ref.
**Date:** 2026-10-05.
**Requirement audited:** RQ-002 in `docs/PILOT1_READY_QUEUE.md` and Phase 11 of `docs/PILOT1_EXECUTION_CHECKLIST.md`. RQ-002 asks for a persistent bottom-right Ask Aria using the **same governed Aria**, page-aware, permission-scoped, truthful, opened by click with no wake word, with voice where supported, and exposing no private data on public pages.

---

## 1. Findings (questions 1–14)

**1. Where does the button come from?**
- `frontend/src/components/admin/AdminAria.jsx`. The closed state is a `fixed bottom-6 right-6` button labelled "Ask Aria" (`data-testid="admin-aria-open"`).
- It is rendered once at the root of `frontend/src/pages/Admin.jsx`: `<AdminAria currentSection={activeTab} onNavigate={setActiveTab} />` plus `<AriaSpotlight />`.

**2. Which pages show it?**
- **Only `/admin`**, which is `Protected adminOnly` in `frontend/src/App.js`.
- These pages do **not** show it:
  - signed-in: `/staff`, `/workspace`, `/alerts`, `/front-desk`, `/admin/blueprint`, `/admin/install`, `/admin/help`, `/aria`;
  - public: `/`, `/experience`, `/for-communities`, `/for-residents`, `/login`, `/kiosk/:id`, `/family/:token`.
- `git grep "AdminAria"` shows the component is used only in `Admin.jsx`.

**3. Is it the same governed Aria?** **No — it is a separate assistant.**
- `AdminAria.jsx` posts to `POST /api/admin-assistant/chat`, served by `backend/routes/admin_assistant.py`.
- That route uses OpenAI chat-completions (`OPENAI_TEXT_MODEL`, default `gpt-4o-mini`).
- Its system prompt says: *"You are Aria … a DIFFERENT context from the resident-facing companion and the personal operator build."*
- Its tool catalog (`admin_assistant_tools.py`) is separate.
- Resident Aria is a different system: OpenAI Realtime via `backend/routes/realtime_resident_session.py` and `realtime_companion_prompt.py`, with tools from `realtime_tools.py`.
- The owner's Aria is a third: `realtime.py::_build_aria_instructions` at `/realtime/aria-session`.
- `docs/ARIA_CONTRACT.md` is still a placeholder. Its 2026-09-23 factual note records that Aria's identity text lives in four places.
- **What is governed in Admin Aria:**
  - Tools call the real route handlers in-process (`admin_assistant_executor.py`). Mutations write receipts with `source="aria_admin"`.
  - Every turn is logged to `routes.events` under a `conversation_id` and a `request_id`.
- **What is not:**
  - It does not use the `ActorContext` / `task_lifecycle` path (`actor_context.py`, `task_lifecycle.py`). Today that path covers task and ride state only.

**4. What page context does Aria receive?** Only `current_section`, which is the Admin tab value. It is inserted in the prompt as *"The administrator is currently looking at the "<section>" section."* (`admin_assistant.py::_build_system_prompt`). It also gets the active facility name. No route, record id or selection is passed.

**5. Does open/close preserve page state?** On `/admin`, yes:
- The panel sits outside `<Tabs>`, so it survives tab switches. Its open/closed state and messages are React state.
- Navigation happens only through returned `ui_actions` (`adminAriaActions.js`).
- A page reload starts a new conversation. This is documented in the component.

**6. On signed-in pages:**
- **User and role context:**
  - The bearer token gives the backend the user; the route requires `require_admin` (owner or admin).
  - The model is told only the section and the facility, not the user's role.
  - Tool calls pass the admin user object to the route handlers (`list_residents(user=admin_user)`, etc.).
- **Permission scope:** there is only one tier, admin. No staff, department or front-desk assistant or tool set exists.
- **Reaching data outside the role:**
  - A non-admin cannot call `/admin-assistant/chat`; it returns 403 through `require_admin`.
  - Inside the admin tier, the tools reach every resident, room and device. That is equivalent to the Admin UI.

**7. On public pages:**
- **Tools:** no Ask Aria and no assistant tools exist on public pages.
- **Private data reachable without signing in — present today, independent of RQ-002:**
  - **(a) Owner memory.** `POST /api/realtime/aria-session` in `backend/routes/realtime.py` has no authentication dependency.
    - It takes `owner_user_id` from the request body.
    - It builds instructions with `build_aria_context_block(owner_user_id)` (`aria_memory.py`), which reads that owner's standing facts and episodic notes from `db.aria_memories`.
    - It returns those instructions in the response as `_caos.instructions`.
    - The same data is owner-only through `GET /api/aria/memory/{owner_user_id}/context` (`require_owner`), so this endpoint bypasses that protection.
    - **This is a code finding, not tested against the live site.**
  - **(b) Resident context.** These endpoints are public and keyed only by `resident_id` / `room` / `session_id`, by design (the kiosk trust model):
    - `GET /api/aria/continuity` (`aria_continuity.py`) returns the resident's own prior words verbatim.
    - `/api/aria/operational-state`, `/api/aria/conversation-state` and `/api/aria/interpretation-patterns` (plus `/match`).
  - **(c) Unauthenticated write.** `POST /api/aria/conversation-turn` (`aria_memory.py`) has no authentication.
- **Consequence for RQ-002:** a public-page Ask Aria must call **none** of the endpoints above. It needs a path limited to public product knowledge.

**8. Which text conversation path works today?**
- `AdminAria` → `POST /api/admin-assistant/chat` → chat-completions tool loop (at most 6 rounds) → reply + `ui_actions`. Admin only.
- The kiosk also accepts typed turns into the live Realtime session (`frontend/src/lib/realtimeTypedTurn.js`, demo kiosk).

**9. Which realtime / full-duplex voice paths exist?**
- **Resident kiosk:** `POST /api/realtime/session` → `realtime_resident_session.py`; WebRTC through `POST /api/realtime/negotiate`; client in `frontend/src/lib/useRealtimeVoice.js` / `realtimeConnection.js` / `realtimeMessageHandler.js`. It is full-duplex with barge-in. Tools execute in the browser against public endpoints.
- **Owner `/aria`:** `AriaVoice.jsx` → `/realtime/aria-session`. This is the unauthenticated endpoint from §7(a).
- **Room:** the Voice PE endpoint (firmware lane), outside this frontend.

**10. Is the microphone wired into Ask Aria?** **No.** `AdminAria.jsx` contains no `getUserMedia` or voice code; it is text only by design (its own header comment).

**11. Does it need a wake word?** **No.** The button opens the panel on click (`setOpen(true)`). The wake-word client (`useWakeWord`, `?wake=1`) exists only in `Kiosk.jsx`.

**12. Which files would need to change?**
- **New:**
  - a shared `frontend/src/components/AskAria.jsx`, generalized from `AdminAria.jsx`;
  - a public-knowledge assistant route;
  - per-role tool catalogs.
- **Modified:**
  - `frontend/src/App.js`: mount once at the app/layout level, so no individual page needs editing;
  - `frontend/src/pages/Admin.jsx`: switch to the shared component;
  - `backend/routes/admin_assistant.py`, `admin_assistant_tools.py` and `admin_assistant_executor.py`: generalize into one assistant with per-role tools;
  - `backend/server.py`: router registration;
  - for voice (phase b): `backend/routes/realtime.py` (an authenticated staff session) and `frontend/src/lib/useRealtimeVoice.js`.
- **Docs:** `docs/ARIA_CONTRACT.md` for a single identity. This needs Michael.
- **Fix before or alongside:** authentication on `/realtime/aria-session` (§7a) and a decision on the §7(b)/(c) endpoints. These belong to Shared Core / the Aria lane, not the RQ-002 implementer.

**13. Overlaps with other lanes:**
- **Agent Four SC-8/SC-9 (PR #59, `pilot/shared-core-sc8-sc9` @ `eb5b7be`, open):** touches `models.py`, `departments.py`, `notifications.py`, `resident_requests.py`, `tasks.py`, `transportation.py`, `transportation_assign.py`, `DepartmentWorkspace.jsx`, `DepartmentWorkspaceDialog.jsx`.
  - A page-by-page mount would collide on `DepartmentWorkspace.jsx`.
  - Any department task tool would call `task_actions` / `task_lifecycle` (Shared Core), not modify them.
  - **An app-level mount has no file overlap.**
- **Agent Three SIM-4 (`pilot/sim-4-nursing`, not yet on GitHub):** scope is `backend/simulation/*`, `backend/routes/simulation.py` and the simulator frontend. **No overlap.**
- **Wake research (PR #46 `research/wake-phrase-funnel`; Agent Two's A/B):** only `firmware/voice-pe-aria/**` and `tools/`. **No overlap.**
- **Demo continuity (`pilot/rq-001-demo-continuity` @ `797961f`):** 0 commits ahead of integration and no pending code diff. **No overlap.** If RQ-001 is reworked onto `Kiosk.jsx` or `demo_kiosk.py`, Ask Aria should stay off `/kiosk`.

**14. Acceptance tests that should prove RQ-002:**
1. **Presence:** the button is visible on every intended route (decided per role) and absent where excluded (e.g. `/kiosk`). It opens with one click/tap and no wake word.
2. **Page state:** opening and closing keeps the route, tab, scroll and form state. The conversation survives in-app navigation.
3. **Same Aria:** one identity source is used by the admin, staff and public variants. A test asserts the same identity block appears in each variant's prompt.
4. **Permission scope:** each role receives only its own tool set. A staff user's call to an admin-only tool returns 403 and writes nothing. Department staff see only their department's requests.
5. **Truthful actions:** every mutation produces a receipt chained to its origin. Aria never confirms an action without a receipt or a verified read-back. A failed tool call is reported as failed.
6. **Public isolation:** on public pages the assistant makes zero calls to resident, owner, `/aria/*` or `/realtime/*` endpoints (network assertion). Answers use public product knowledge only, so no resident name, room or conversation appears.
7. **Voice (phase b):** an authenticated session minted only for a signed-in user; full-duplex with barge-in; the mic is released on close; no wake word.
8. **Layout:** usable at 390 px; the panel doesn't cover primary actions.
9. **Regression:** the backend gate stays at zero known failures and the frontend suite and build pass.

---

## 2. What already satisfies RQ-002

- A persistent bottom-right entry point that opens without a wake word (admin only).
- Section awareness, and on-screen navigation through `ui_actions`.
- Server-side tool execution through the real route handlers, with receipts and event logging.

## 3. Result: **WAITING** — exact blockers

1. **"Same governed Aria" is undefined.** Four separate Aria prompt sources exist and `docs/ARIA_CONTRACT.md` is empty. **Michael must decide** which identity and governance the global button carries (owner of that decision: Michael + the Aria lane).
2. **A known private-context exposure exists** at `/realtime/aria-session` (§7a). RQ-002 adds a public entry point, so this should be fixed first as its own Shared Core / security item, not inside RQ-002. §7(b)/(c) need a stated decision on the kiosk trust model.
3. **PR #59 (SC-8/SC-9) is open** and touches `DepartmentWorkspace.jsx`. RQ-002 must either wait for its merge or commit to an app-level mount only.
4. **The gate condition is still unmet:** the coordinator has not confirmed that the Shared Core + Demo kiosk contracts are stable.

## 4. Proposed shape once the blockers clear (for the coordinator; not started)

- **RQ-002a, text first.** Branch `feature/rq-002a-global-ask-aria`. Owned files:
  - `frontend/src/components/AskAria.jsx` (new);
  - `frontend/src/lib/askAria*.js` (new);
  - an app-level mount in `frontend/src/App.js`;
  - `frontend/src/pages/Admin.jsx` (swap the component);
  - `backend/routes/aria_assistant*.py` (new; generalizes `admin_assistant*.py`, which it would then replace);
  - `backend/server.py` (router line);
  - tests.
  - Shared Core keeps `task_*`, `actor_context.py` and `models.py`. The Aria lane keeps prompt identity.
- **RQ-002b, voice.** An authenticated Realtime session with server-side tool execution. Start after RQ-002a is accepted.
