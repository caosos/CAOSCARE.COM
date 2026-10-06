# Security follow-up — `/aria/conversation-turn` and public resident context (read-only)

**Auditor:** Agent Six (Claude Code, Opus 5.5).
**Ref inspected:** `integration/2026-09-27` @ `7136734`, which already includes PR #64 (the `/realtime/aria-session` fix).
**Production source:** `d7ff96a`. Each finding below states whether it is also present there.
**Date:** 2026-10-06.
**Method:** code inspection only. Nothing was edited, no live endpoint was probed, and no test was run against production.
**Follows:** RQ-002 audit (#61) and security fix #64.

| Item | Route(s) | Severity | Blocks Pilot 1? |
|---|---|---|---|
| A | `POST /api/aria/conversation-turn` | **Low–Medium** | No (cheap to fix with A-fix) |
| B1 | Public resident context reads | **High** | **Yes** |
| B2 | `POST /api/aria/interpretation-patterns/confirm` | **High** | **Yes** |
| C | `GET /api/residents/public/by-kiosk/{id}` + `GET /api/kiosks` (found during B) | **Critical** | **Yes** |

**Ranking:** C is the most urgent (medical notes readable without login). B2 and B1 come next. A last.

---

## A. `/aria/conversation-turn` — tampering

**Route and files:**
- `backend/routes/aria_memory.py::ingest_conversation_turn` (`AriaConversationTurnIngest`: `owner_user_id`, `session_id`, `role`, `content`).
- Caller: `frontend/src/lib/realtimeMessageHandler.js` (~line 124), only when the session context carries `owner_user_id` (the owner `/aria` build).
- Present in production `d7ff96a`.

**Auth model:** none. No dependency and no token check. The owner id comes from the body.

**Data exposed or changeable:**
- **Write only.** Anyone can insert turns with any `role` and any `content` (no length limit) under any `owner_user_id` and `session_id` into `db.aria_conversations`.
- The only readers are the owner-only viewer routes in the same file: `GET /aria/conversation-threads/{owner_user_id}` and `.../{session_id}` (both `require_owner`), shown on the `/aria` page under "Past conversations".
- `git grep aria_conversations` finds no other reader. These turns do **not** feed Aria's instructions, operator memory (`db.aria_memories`) or any extraction. So there is **no model or prompt influence and no disclosure.**

**Exploit preconditions:**
- Network reach to the API.
- To land in the real owner's viewer, the owner's `user_id`. User ids are opaque (`user_<hex>`), are not secret by design, and before #64 could be learned through `/aria-session`.
- With any random id, the attacker can still write unbounded junk: storage and denial-of-service by volume. No rate limit exists (`git grep ratelimit` finds only `family_portal.py`).

**Severity: Low–Medium.** Integrity of the owner's own transcript history, plus storage abuse. No confidentiality impact. No resident impact.

**Smallest safe fix:**
- `ingest_conversation_turn(data, user=Depends(require_owner))`. Store `owner_user_id = user["user_id"]`; refuse a body id that names someone else (same pattern as #64).
- Add `max_length` on `content` (e.g. 4000) and restrict `role` to `{"user", "assistant"}`.
- Frontend: the owner-turn `fetch` in `realtimeMessageHandler.js` must send the signed-in token. Reuse #64's `sessionAuth` opt-in (thread it through `ctxRef` / the connection), or add an `Authorization` header only in the `ownerId` branch.
- Resident turns are unaffected; they go to `/memory/realtime-turn`.

**Tests:**
- Anonymous → 401 and nothing stored.
- Staff/admin → 403.
- Owner → stored under the authenticated id.
- A forged body id → 403.
- Oversize content → 422.
- Bad role → 422.
- In-process with a scratch DB, like `test_realtime_aria_session_auth.py`.

**Blocks Pilot 1:** No. The owner build is not part of the resident pilot. Fixing it alongside #64's follow-up costs little.

---

## B1. Public resident context reads

**Routes and files:**
- `GET /api/aria/continuity` (`aria_continuity.py`)
- `GET /api/aria/operational-state` (`aria_operational_state.py`)
- `GET /api/aria/conversation-state` (`aria_conversation_state.py`)
- `GET /api/aria/interpretation-patterns` and `GET .../match` (`aria_interpretation_patterns.py`)
- All present in production `d7ff96a`.

**Auth model:** none. The docstrings call them "Public … same trust model as the other resident-facing realtime endpoints … Inspection/debug surface."
- **No frontend code calls any of these GET routes.** `git grep` over `frontend/src` finds no caller.
- The session mint (`realtime_resident_session.py::_mint`) calls the underlying `resolve_*` / `list_patterns` functions **in-process**, not over HTTP.
- So these HTTP routes exist only for inspection.

**Data exposed:**

| Route | Input needed | What it returns |
|---|---|---|
| continuity | `resident_id` | Up to 3 prior sessions from the last 18 h: the resident's own lines **verbatim** and trimmed Aria lines, plus how each session ended |
| operational-state | `resident_id` **or just `room`** | Open alerts and requests: what they're about (from `resident_stated_reason` / `resident_words` / description), lifecycle, age, and **staff names** (`handled_by`) |
| conversation-state | `resident_id` + `session_id` | Request references and state for one session |
| interpretation-patterns / match | `resident_id` | Confirmed heard → understood pairs (speech habits, language learning) |

**Exploit preconditions:** network reach, plus:
- a room number, which is guessable (e.g. `214`);
- or a `resident_id`, which takes **no guessing**: public `GET /api/kiosks` lists every kiosk with its room, and public `GET /api/residents/public/by-kiosk/{kiosk_id}` returns the room's resident (item C).
- So every resident can be enumerated without a login.

**Severity: High.** A resident's private words and care requests can be read over the internet, in a senior-care product.

**Smallest safe fix:**
- Add `Depends(require_admin)` to these five GET routes, or remove them. Nothing outside debugging uses them, and the mint path is in-process and unaffected.
- Update `tests/test_aria_operational_state.py::test_operational_state_http_endpoint`, which currently calls the route without auth over HTTP.

**Tests:**
- For each route: anonymous → 401, staff → 403, admin → 200.
- A resident session mint still contains the continuity / operational / interpretation blocks (assert on `_caos.instructions`, with OpenAI mocked as in #64).

**Blocks Pilot 1: Yes.** Real residents' words and requests would be readable without a login.

---

## B2. `POST /api/aria/interpretation-patterns/confirm` — poisoning a resident's Aria instructions

**Route and files:**
- `aria_interpretation_patterns.py::confirm_interpretation_pattern` → `record_pattern(ConfirmInterpretationInput)`.
- Caller: the kiosk browser's `confirm_interpretation_pattern` tool, `frontend/src/lib/realtimeOperationsTools.js` (~line 266).
- Present in production `d7ff96a`.

**Auth model:** none. It takes `resident_id` from the body, and `source` (`resident_confirmed` / `staff_entered` / `inferred`) is also taken from the body.

**Data changeable:**
- Anyone can create or overwrite up to `MAX_PATTERNS_IN_CONTEXT` (15) patterns for any resident.
- `heard_as`, `understood_as` and `meaning` have no length or content limits.
- `_mint` loads these patterns (`list_patterns`) and `render_interpretation_block` writes them into that resident's **Aria instructions** under "CONFIRMED person-specific patterns".
- **This is a direct prompt-injection path into a vulnerable resident's assistant.** It can make Aria misunderstand ("help" heard as something else) or carry instruction-like text, and the forged `source` makes it look staff-entered.

**Exploit preconditions:** network reach plus a `resident_id`, obtainable through C.

**Severity: High.** Integrity of resident-facing safety behaviour.

**Smallest safe fix:** the kiosk is not logged in, so a plain auth gate would break the legitimate tool. The fix is to **ground the write in a live session**:
1. The request must carry the `session_id` of an **active Aria room lease** (`resident_aria_leases`) for that same resident's room.
2. `heard_as` must appear in a **recent resident turn of that session** in `db.conversations`. This is the same grounding technique as the TSB-001 / `update_preferred_name` guards.
3. `source` is set on the server (`resident_confirmed` for this path); the body cannot set it.
4. Length limits (e.g. 200 characters each). In `render_interpretation_block`, strip newlines and markdown headings so a pattern cannot open a new instruction section.
5. Staff entry, if wanted, becomes a separate authenticated route.

**Tests:**
- No session → 403.
- Session for a different resident → 403.
- `heard_as` not said in that session → 403.
- Grounded confirmation → stored with `source="resident_confirmed"` whatever the body says.
- Overlong field → 422.
- Injected newline or `##` text is neutralised in the rendered block.

**Blocks Pilot 1: Yes.**

---

## C. (found during B) `GET /api/residents/public/by-kiosk/{kiosk_id}` + `GET /api/kiosks`

**Routes and files:**
- `backend/routes/residents.py::resident_by_kiosk` returns `{"kiosk": kiosk, "resident": resident}` with the **whole resident document**. The only projection is `{"_id": 0}`.
- `backend/routes/kiosks.py::list_kiosks` is public ("kiosks need to self-identify without auth").
- Both present in production `d7ff96a`.

**Data exposed:** every `Resident` field (`models.py`), including:
- `medical_notes`
- `emergency_contact`
- `date_of_birth`
- `clinical_thresholds`
- `memory` (notes for the AI)
- `preferences`
- `photo`
- `pendant_id`

…for **every** resident, by walking the public kiosk list.

**What the kiosk actually needs:** `Kiosk.jsx` / `RealtimeChatScreen.jsx` / `components/kiosk` read only `resident.resident_id`, `resident.name`, `resident.preferred_name` and `resident.room` (`git grep` over those files).

**Severity: Critical.** Health-related personal information, unauthenticated, with enumeration of every resident.

**Smallest safe fix:**
- An allowlist projection in `resident_by_kiosk`: `resident_id`, `name`, `preferred_name`, `room`, `participation_level`, `synthetic`.
- Keep the `kiosk` object as is, or trim it as well.
- Separately decide whether `GET /api/kiosks` needs to stay public. The kiosk only needs its own record, not the list.

**Tests:**
- The response contains none of `medical_notes`, `emergency_contact`, `date_of_birth`, `clinical_thresholds`, `memory`, `preferences`, `photo`, `pendant_id`, and does contain the four fields the kiosk uses.
- The kiosk page still loads a resident (the existing frontend tests plus one route test).

**Blocks Pilot 1: Yes.**

---

## Related, not assessed in depth

- `POST /api/memory/realtime-turn` (resident turn ingest) is public by the same kiosk model. It writes `db.conversations` (which continuity reads) and triggers memory extraction into `db.memories` (which goes into the resident prompt). That is a second write path into a resident's context. Recommend reviewing it together with B2's session-grounding approach.
- The structural fix for all of B and C is a **kiosk device credential**. `routes/device_auth.py` and the `DEVICE_AUTH_REQUIRED` setting exist; that is longer-term work.

## Recommended order (each a separate, isolated fix awaiting coordinator authorization)

1. **C:** a one-function projection allowlist. Smallest change, largest exposure.
2. **B1:** admin-gate the five GET inspection routes.
3. **B2:** session-grounded confirm write + render sanitising.
4. **A:** owner-only turn ingest + owner turn POST sends the token.

All four exist in production `d7ff96a`. Deploying any fix needs Michael's release approval.
