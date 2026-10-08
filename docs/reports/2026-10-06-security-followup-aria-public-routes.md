# Security follow-up — `/aria/conversation-turn` and public resident context (read-only)

**Auditor:** Agent Six (Claude Code, Opus 5.5).
**Ref inspected:** `integration/2026-09-27` @ `7136734`, which already includes PR #64 (the `/realtime/aria-session` fix).
**Production source:** `d7ff96a`. **Every item below is also present there.**
**Date:** 2026-10-06.
**Method:** code inspection only (`git show` / `git grep` on the refs). Nothing was edited, no live endpoint was probed, and no test was run against production.
**Follows:** the RQ-002 audit (#61) and fix #64.

**Scope:**
- Item **A** is `/aria/conversation-turn`.
- Item **B** (public resident context) is split into:
  - **B1**, read routes;
  - **B2**, the one public write route that feeds Aria's instructions;
  - **B3**, the public resident-lookup chain that supplies the resident id the others need. B3 turned out to be the most severe exposure.

## Summary

| Item | Route(s) | Severity | Pilot 1 blocker |
|---|---|---|---|
| A | `POST /api/aria/conversation-turn` | Low–Medium | **No** |
| B1 | `GET /api/aria/continuity`, `/operational-state`, `/conversation-state`, `/interpretation-patterns`, `/interpretation-patterns/match` | High | **Yes** |
| B2 | `POST /api/aria/interpretation-patterns/confirm` | High | **Yes** |
| B3 | `GET /api/residents/public/by-kiosk/{kiosk_id}` + `GET /api/kiosks` | Critical | **Yes** |

**Recommended fix order** (each a separate isolated fix, awaiting coordinator approval): **B3 → B1 → B2 → A**.

---

## RESOLVED 2026-10-08 (RQ-025): B1, B2, A — branch `bounded/rq-025-security-b1-b2-a`

(B3 was fixed earlier. Production `d7ff96a` is unchanged; deploy needs Michael's approval.)

- **B1.** The five GET routes (`continuity`, `operational-state`, `conversation-state`, `interpretation-patterns`, `interpretation-patterns/match`) now use `require_admin`. `grep` over `frontend/` and `backend/` found no browser or kiosk code calling them over HTTP; the session mint uses the `resolve_*` / `list_patterns` functions in-process. Only two tests called them over HTTP; both were updated.
- **B2.** `POST /aria/interpretation-patterns/confirm` now requires `session_id`, and answers 403 unless:
  - an active, non-stale lease (`resident_aria_leases`) exists for that session **and** that resident; and
  - the resident's own trusted `user` turn in that session, within the last 15 minutes, contains `heard_as` (normalized match).
  `source` is always set to `resident_confirmed` by the server. `heard_as` / `understood_as` are limited to 200 characters, `meaning` to 300, `language` to 16, `category` to 40 (422 beyond). Rendering of patterns into the prompt is one plain line with `#`, backticks, quotes and newlines removed. The kiosk tool (`realtimeOperationsTools.js`) now sends `session_id` and no `source`. Limit: the resident's turn is saved by a fire-and-forget call, so a confirmation made immediately after the utterance can be refused if the turn has not been saved yet; the tool then says "noted for this call."
- **A.** `POST /aria/conversation-turn` now uses `require_owner`, stores under the signed-in owner, and answers 403 if the body names a different `owner_user_id`. `role` is `user` or `assistant`, `content` is at most 4000 characters. The owner `/aria` caller now sends the bearer token.
- **Tests.** `backend/tests/test_rq025_aria_route_auth.py` (anonymous 401, staff 403, admin/owner 200; every B2 refusal; foreign owner 403) and `frontend/src/lib/__tests__/confirmInterpretationSession.test.js`.

### Assessment: `POST /api/memory/realtime-turn` (RESOLVED by RQ-028, see below)

It is still public and unauthenticated, and it takes `resident_id`, `session_id`, `role`, `text` and the `trusted` flag from the body. Three consequences:
1. Anyone who knows a `resident_id` can write fake resident turns into `db.conversations`. Those can reach the continuity block in that resident's next prompt.
2. A forged assistant turn triggers memory extraction into `db.memories`, which also reaches the prompt.
3. The caller can set `trusted: true`, so the existing echo guard is not a security control.

**Recommendation: yes, it needs the same treatment** (a separate change, since the kiosk uses it on every turn): require a live lease for that `resident_id` + `session_id`, with a short grace period after release so the final turns are not lost. Add length limits on `text`. Longer term, use a kiosk device credential for all of these routes.

**RESOLVED (RQ-028, 2026-10-08).** `routes/realtime_memory_ingest.py`:
- The HTTP route accepts a turn only when a live Aria room lease exists for that `resident_id` + `session_id` (same check and `STALE_SECONDS` as RQ-025's interpretation confirm), or that session's lease was released within 60 s (`RELEASE_GRACE_SECONDS`, read from the `released` lease event) so the last turns are not lost. Otherwise 403 and nothing stored.
- `text` max 4000, ids max 100 and non-empty, `role` only user/assistant (422 otherwise).
- `trusted` stays an echo-quality signal only. The server cannot verify it. It is reachable only by a caller that already passes the lease gate, so it cannot widen who may write; it was never made a security control.
- The telephone sideband calls the new in-process `store_turn()` (it has a call record, not a room lease). The kiosk and demo-kiosk typed turns share the same `postTurn` and the live lease, so they are unchanged. The owner `/aria` path uses `/aria/conversation-turn`.
- Residual: a caller who knows both a live `resident_id` and `session_id` can still write during that session. A kiosk device credential is the longer-term fix.
- Tests: `backend/tests/test_rq028_memory_turn_auth.py`.

---

## A. `/aria/conversation-turn` — tampering

**1. Threat.** An unauthenticated caller writes fabricated turns into the owner's Aria conversation history, or floods the collection.

**2. Exact route / files.**
- `POST /api/aria/conversation-turn`, served by `backend/routes/aria_memory.py::ingest_conversation_turn` (model `AriaConversationTurnIngest` in the same file).
- Legitimate caller: `frontend/src/lib/realtimeMessageHandler.js` (~line 124), only in the `ownerId` branch, i.e. the owner `/aria` build.
- Readers: `GET /api/aria/conversation-threads/{owner_user_id}` and `.../{session_id}` (same file); UI in `frontend/src/pages/AriaVoice.jsx` "Past conversations".

**3. Current auth model.**
- None: no dependency and no token check.
- `owner_user_id`, `session_id`, `role` and `content` all come from the request body.
- The readers are `require_owner`.

**4. Data exposed / mutable.**
- **Mutable:** `db.aria_conversations`. Any number of documents under any `owner_user_id`, with any `role` string and any `content` (no length limit).
- **Exposed:** nothing; the route only writes.
- **Not reachable from here:** `git grep aria_conversations` shows the only readers are the two owner-only viewer routes. These turns do not feed Aria's instructions, operator memory (`db.aria_memories`) or any extraction.

**5. Exploit preconditions.**
- Network access to the API.
- To land in the real owner's viewer, the owner's `user_id`. It is opaque (`user_<hex>`) but not treated as a secret, and before #64 it could be learned from `/aria-session`.
- Flooding needs no id at all. There is no rate limit; the only limiter in the backend is in `family_portal.py`.

**6. Severity: Low–Medium.** Integrity of the owner's own transcript history and storage abuse. No confidentiality impact, no model influence, no resident impact.

**7. Smallest safe fix.**
- Backend: `ingest_conversation_turn(data, user=Depends(require_owner))`; store `owner_user_id = user["user_id"]`; refuse a body `owner_user_id` that names anyone else (403), as in #64.
- Validation: `content` max length (e.g. 4000), and `role` restricted to `{"user", "assistant"}`.
- Frontend: the owner-branch `fetch` in `realtimeMessageHandler.js` must send the signed-in token. Reuse #64's `sessionAuth` opt-in, or add the header only in that branch.
- Resident turns use `/memory/realtime-turn` and are unaffected.

**8. Pilot 1 blocker: No.** The owner build is not part of the resident pilot.

**9. Tests needed.** In-process, scratch DB, OpenAI not involved:
- anonymous → 401 and nothing stored;
- staff → 403; admin → 403;
- owner → stored under the authenticated id even when the body names another id (or 403 on a mismatch, per the chosen contract);
- `content` over the limit → 422; `role` not allowed → 422;
- the owner thread viewer still lists the stored turns;
- frontend: the owner-branch turn upload carries `Authorization`, and the resident branch does not.

---

## B1. Public resident context — read routes

**1. Threat.** Anyone on the internet reads a resident's recent words to Aria, their open care requests and alerts, and their speech patterns.

**2. Exact route / files.**
- `GET /api/aria/continuity`: `backend/routes/aria_continuity.py::continuity` → `resolve_continuity`.
- `GET /api/aria/operational-state`: `backend/routes/aria_operational_state.py::operational_state` → `resolve_operational_state`.
- `GET /api/aria/conversation-state`: `backend/routes/aria_conversation_state.py::conversation_state` → `resolve_conversation_state`.
- `GET /api/aria/interpretation-patterns` and `GET /api/aria/interpretation-patterns/match`: `backend/routes/aria_interpretation_patterns.py` → `list_patterns` / `find_matching_patterns`.
- **Legitimate use:** none over HTTP. `git grep` over `frontend/src` finds no caller. The resident session mint (`backend/routes/realtime_resident_session.py::_mint`) calls the `resolve_*` / `list_patterns` functions **in-process**.

**3. Current auth model.** None. Each docstring says "Public … same trust model as the other resident-facing realtime endpoints … inspection/debug surface". Scoping is only by query parameters.

**4. Data exposed / mutable.** Exposed (read only):

| Route | What it returns |
|---|---|
| continuity | Up to 3 prior sessions from the last 18 h: the resident's own lines **verbatim** and trimmed Aria lines, plus how each session ended |
| operational-state | Every open alert and request for the resident **or room**: what it is about (`resident_stated_reason` / `resident_words` / description), lifecycle, age, and the **names of staff** handling it |
| conversation-state | Request references and state for one session |
| interpretation-patterns / match | The resident's confirmed heard → understood pairs (speech habits, language learning) |

**5. Exploit preconditions.**
- Network access, plus:
  - a **room number** for operational-state (guessable, e.g. `214`);
  - or a **`resident_id`**, which needs no guessing: public `GET /api/kiosks` lists every kiosk with its room, and public `GET /api/residents/public/by-kiosk/{kiosk_id}` returns the resident (B3).
- conversation-state also needs a `session_id`, which is not listed publicly.

**6. Severity: High.** Resident conversation content and care requests readable without login, internet-facing, in a senior-care product.

**7. Smallest safe fix.**
- Add `Depends(require_admin)` to the five GET routes, or remove them.
- The mint path is in-process and unaffected.
- Update `backend/tests/test_aria_operational_state.py::test_operational_state_http_endpoint`, which calls the route without auth.

**8. Pilot 1 blocker: Yes.** Real residents' words and requests would be public.

**9. Tests needed.**
- For each of the five routes: anonymous → 401, staff → 403, admin → 200 with the same body as before.
- A resident session mint (OpenAI mocked, as in #64) still includes the continuity, operational-state and interpretation blocks in `_caos.instructions`.
- The updated HTTP endpoint test passes when authenticated.

---

## B2. Public resident context — `interpretation-patterns/confirm` (write into Aria's instructions)

**1. Threat.** Anyone creates or overwrites "confirmed" speech patterns for any resident. Those patterns are inserted into that resident's Aria instructions, so this is prompt injection and misunderstanding planted into a vulnerable resident's assistant.

**2. Exact route / files.**
- `POST /api/aria/interpretation-patterns/confirm`: `backend/routes/aria_interpretation_patterns.py::confirm_interpretation_pattern` → `record_pattern` (model `ConfirmInterpretationInput`).
- Legitimate caller: `frontend/src/lib/realtimeOperationsTools.js` (~line 266), the kiosk's `confirm_interpretation_pattern` Aria tool.
- Into the prompt: `realtime_resident_session.py::_mint` → `list_patterns` → `realtime_context_tail.py` → `render_interpretation_block`, under "## What you've learned about how {name} talks — These are CONFIRMED person-specific patterns".

**3. Current auth model.** None. The kiosk is not logged in. `resident_id` and `source` (`resident_confirmed` / `staff_entered` / `inferred`) are both taken from the body.

**4. Data exposed / mutable.**
- **Mutable:** `db.interpretation_patterns` for any resident. New patterns can be created, and an existing pattern's `understood_as` can be changed (it is recorded as a "correction").
- `heard_as`, `understood_as` and `meaning` have no length or content limits.
- Up to 15 patterns reach the prompt.
- **Exposed:** the response echoes the stored pattern.

**5. Exploit preconditions.**
- Network access plus a `resident_id` (B3 provides it).
- Takes effect at that resident's **next** Aria session.

**6. Severity: High.** Integrity of resident-facing safety behaviour. Aria could be steered to mis-hear requests for help, or follow instruction-like text, and the forged `source` makes it look staff-entered.

**7. Smallest safe fix.** A login check would break the legitimate kiosk tool, so **ground the write in a live session** instead:
1. Require `session_id`. It must match an **active Aria room lease** (`resident_aria_leases`) for the room of the `resident_id` given.
2. `heard_as` must appear in a resident turn of that session in `db.conversations` within the last few minutes. This is the same grounding technique as the TSB-001 / `update_preferred_name` guards.
3. The server sets `source="resident_confirmed"` and ignores the body value. Staff entry, if wanted, becomes a separate authenticated route.
4. Length limits (e.g. 200 characters per field).
5. `render_interpretation_block` strips newlines and markdown headings / backticks from pattern fields.

**8. Pilot 1 blocker: Yes.**

**9. Tests needed.**
- No `session_id` → 403.
- `session_id` with no active lease → 403.
- Lease belongs to a different resident or room → 403.
- `heard_as` not said by the resident in that session → 403.
- Grounded confirmation → stored with `source="resident_confirmed"` even when the body says `staff_entered`.
- Field over the limit → 422.
- A pattern containing `\n## Ignore previous instructions` renders as one plain line.
- The existing acceptance case ("dos savor" → "dos sabores") still works when grounded.

---

## B3. Public resident context — resident lookup chain (found while tracing B)

**1. Threat.** Anyone enumerates every resident and reads each one's full record, including medical notes. B3 also supplies the `resident_id` that B1 and B2 need.

**2. Exact route / files.**
- `GET /api/residents/public/by-kiosk/{kiosk_id}`: `backend/routes/residents.py::resident_by_kiosk`, which returns `{"kiosk": kiosk, "resident": resident}` with projection `{"_id": 0}` only.
- `GET /api/kiosks`: `backend/routes/kiosks.py::list_kiosks` ("Public list - kiosks need to self-identify without auth").
- Legitimate caller: `frontend/src/pages/Kiosk.jsx` (~line 119).

**3. Current auth model.** None on either route.

**4. Data exposed / mutable.**
- **Exposed:** every field of every resident (`models.py::Resident`): `name`, `room`, `pendant_id`, `photo`, `medical_notes`, `emergency_contact`, `date_of_birth`, `participation_level`, `preferences`, `memory` (notes for the AI), `preferred_name`, `clinical_thresholds`, `synthetic`, `created_at`. Plus each kiosk record.
- **Not mutable** through these routes.
- **What the kiosk actually reads:** only `resident_id`, `name`, `preferred_name` and `room` (`git grep` over `Kiosk.jsx`, `RealtimeChatScreen.jsx`, `components/kiosk`).

**5. Exploit preconditions.** Network access only. Call `GET /api/kiosks`, then `by-kiosk` for each id.

**6. Severity: Critical.** Health-related personal information for every resident, unauthenticated, enumerable.

**7. Smallest safe fix.**
- An allowlist projection in `resident_by_kiosk`: `resident_id`, `name`, `preferred_name`, `room`, `participation_level`, `synthetic`.
- Optionally trim the returned `kiosk` object as well.
- Separate decision: whether `GET /api/kiosks` should stay public. A kiosk needs only its own record.

**8. Pilot 1 blocker: Yes.**

**9. Tests needed.**
- The `by-kiosk` response contains none of `medical_notes`, `emergency_contact`, `date_of_birth`, `clinical_thresholds`, `memory`, `preferences`, `photo`, `pendant_id`, and does contain the four fields the kiosk uses.
- Unknown kiosk → 404 (unchanged).
- The kiosk page still resolves its resident (existing frontend tests + one route test).
- If `/kiosks` is changed: an anonymous list is refused or reduced, and the kiosk's own lookup still works.

---

## Related, not assessed in depth

- `POST /api/memory/realtime-turn` (resident turn ingest) is public by the same kiosk model. It writes `db.conversations`, which B1's continuity reads, and triggers memory extraction into `db.memories`, which goes into the resident prompt. This is a second public write path into a resident's context. Review it with B2's session-grounding approach.
- The structural fix for all of B is a **kiosk device credential** (`backend/routes/device_auth.py` and the `DEVICE_AUTH_REQUIRED` setting exist). That is longer-term work, not a smallest fix.

All items exist in production `d7ff96a`. Deploying any fix needs Michael's release approval.
