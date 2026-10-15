# Room 214 — ideas from Michael's last substantive conversations with Aria (read-only note, 2026-10-15)

Internal working note. Source: `db.conversations` (Room 214, resident `res_2425767f4a51`, kiosk `kio_dc8c06a19608`) and `db.memories` on the EliteDesk dev database. Nothing here is implemented by this note. Private small talk and personal details are deliberately left out.

## 1. Source sessions

The self-code acceptance session `rt_lnrab36x_1792103482825` (17:31 CDT) was a live test and is **not** the source. The last substantive conversation before it is a two-session thread:

| Session | When (CDT) | Turns stored | What it was |
|---|---|---|---|
| **`rt_1qfrdvtc_1792095382498`** (primary, most recent substantive) | 2026-10-15 15:16–15:21 | 36 | Wake/mic reliability; Michael announces the read-only self-code capability; a refusal loop about owner/creator authority |
| `rt_o5wuoszj_1792034319474` (the substantive one before it) | 2026-10-14 22:18–22:30 | 83 | Room control walk-through, AC protocol problem, "bridge to the system builder" idea, creator identity + memory, personal-assistant ambitions |

Sessions between them (`rt_wwbgyxbp` 13:14 lights/TV commands, `rt_0m9so96n` 16:13 "it should be able to read your code now") carried no new ideas. For completeness, the post-acceptance session `rt_87no5md6_1792104271070` (17:44–17:49, 31 turns) added three capability wishes; they are listed in §9 so they are not lost, but they are outside the "before acceptance" scope Michael set.

Turns reviewed: 36 + 83 (+31 in §9) = 150. Stored conversation summaries in `db.memories` (category `conversation`) for both sessions were cross-checked and are consistent.

## 2. Short factual summary

Michael, speaking to Aria in Room 214 as the product's creator, (a) reported that the wake phrase sometimes needs three or four tries and said he will raise the microphone gain himself; (b) told Aria he was about to give her read-only access to her own code and got stuck in a loop where Aria kept re-stating that she had no such access, which annoyed him ("we've established this", "why do you keep reiterating that?"); (c) the night before, checked the room's AC through Aria (main AC accepted a 72° target; a portable AC is retired/offline; he reported the AC's wireless protocol "doesn't work correctly"), found no menu on file, floated the idea of an adapter/bridge so Aria can file a trouble ticket to the system builder with context, asked Aria to remember that he is the creator so she could later "see the change", and said he wants Aria to become his personal assistant (check email, do things for him).

## 3. Ideas and decisions extracted

| # | Idea / decision | Type | Source |
|---|---|---|---|
| I1 | Room 214 Aria may read her own code, read-only | decision (owner) | rt_1qfrdvtc 15:17–15:20 |
| I2 | Aria must not loop on a limitation once the owner has acknowledged it; in the owner's room she should accept "you don't have it yet, I'm about to change it" without re-reciting the boundary | behaviour / feature request | rt_1qfrdvtc 15:18–15:21; echoed rt_87no5md6 ("I don't need you to iterate what you can do") |
| I3 | Aria should know Michael is the creator/owner and keep that across sessions | memory / identity | rt_o5wuoszj 22:25–22:28; rt_1qfrdvtc 15:17 |
| I4 | Wake reliability: sometimes 3–4 "Hey Aria" tries; Michael adjusts mic gain himself; Aria should not offer a maintenance ticket to the owner for his own hardware | defect report + workflow | rt_1qfrdvtc 15:16–15:17 |
| I5 | A bridge so Aria can file a trouble ticket / feature request to the system builder (developers) with context from the conversation, instead of only staff-department requests | architecture / workflow | rt_o5wuoszj 22:24 |
| I6 | Aria should be able to "note a capability people want" for the team — she said she could, but no such channel exists | truth gap + workflow | rt_87no5md6 22:47 (and I5) |
| I7 | AC: wireless control protocol unreliable; portable AC retired; main AC target set works | defect / device truth | rt_o5wuoszj 22:22–22:23 |
| I8 | Menu not on file for today; Aria offers a kitchen request | data gap (content) | rt_o5wuoszj 22:23 |
| I9 | Aria as Michael's personal assistant: check email, act for him | product direction (owner room) | rt_o5wuoszj 22:28–22:29 |
| I10 | Order a pizza / contact a business; send a text message to someone | capability wish | rt_87no5md6 22:47 (§9) |
| I11 | A sandbox where Aria can write/read small things for Michael, outside the codebase | product idea | rt_87no5md6 22:48 (§9) |
| U1 | Unresolved: how Aria should answer the owner's "you will have X in a moment" without promising the future (truth rule) and without repeating herself | open question | rt_1qfrdvtc 15:19–15:20 |

## 4. Already exists in CAOSCARE

- I1 — **built, loaded and live-accepted** today: PR #169 (`1f60a58`), `docs/ROOM214_SELF_CODE_INSPECTION.md`.
- I3 — memory holds it: pinned fact "Michael Chambers is the human creator and owner of CAOSCARE" (`db.memories`, 2026-10-15) plus a pinned milestone event; Aria said "that's on record" in the 17:44 session. The creator/owner fact therefore persists via lifelong memory (`backend/routes/aria_life_memory.py`, `aria_memory.py`).
- I8 — the Aria information principle (Product Baseline §5) already routes a missing menu to a kitchen request; the gap is content entry, not code.
- Staff-request path for I5's "file it to someone": `request_staff_help` → department queue exists; a *developer/builder* channel does not.

## 5. Partially implemented

- I2 — the owner's `concise_natural` guidance profile exists (`backend/aria_guidance_profiles.py`, 2026-10-13) and the prompt tells Aria not to over-help; nothing tells her to stop re-stating an acknowledged limitation, and the acceptance transcripts show the loop happening twice.
- I4 — wake tuning and the shadow detector exist (`room-node/aria_wake/`, `docs/ARIA_WAKE_WORD_ARCHITECTURE.md`); mic gain is a host PulseAudio setting with no product control and no "owner room" exemption in the "let maintenance know" offer.
- I7 — climate control exists (`adjust_room_temperature`, HA adapters); the Midea AC off-command failure is a known open defect (PROJECT_STATE 2026-10-12 14:45).

## 6. Genuinely new

- I5/I6 — a receipted "note for the builders" channel from a resident/owner conversation into the backlog (GitHub issue or an owner intake record), with Aria only claiming it when the receipt proves it.
- I9/I10/I11 — owner-room assistant actions (email, texting, ordering, a sandbox). None exist; the Product Baseline is explicit that external calls/texts/ordering are not available and Aria must say so. These need an owner decision on scope, providers and safety before any build.
- U1 — a wording rule for "future capability the owner says is coming": acknowledge once, do not promise, do not repeat.

## 7. Suggested future queue items (not started)

1. **Owner-room acknowledged-limit rule** (I2 + U1): in the `concise_natural` profile, once the owner acknowledges a limit, Aria stops restating it and moves on; one sentence if asked again. Acceptance: replay the 15:18–15:21 exchange and the 17:48 exchange against the real prompt builder; no repeated boundary recital. Small, prompt-only, testable with `test_aria_rewake_continuity.py`-style real-prompt tests.
2. **Builder note channel** (I5/I6): `note_for_builders` tool → receipted record (owner intake / GitHub issue via the existing control plane), Room 214 owner room first, truthfully reported. Needs an owner decision on destination.
3. **Owner-hardware exemption for the maintenance offer** (I4): when the resident is the verified owner of the room's hardware, do not offer to page maintenance for it; route to the wake runbook instead. Depends on the owner-room identity already used by self-code.
4. **AC control truth** (I7): record the Midea protocol failure as a device-record fact so Aria states "this AC does not report back / off commands have failed" instead of trying silently. Existing defect; already in PROJECT_STATE.
5. **Personal-assistant scope decision** (I9–I11): owner decision packet before any build (providers, data access, safety, which room). Do not build from this note.

## 8. Provenance

Every row in §3 cites session id and clock time (CDT) of the stored turn in `db.conversations`; summaries cross-checked in `db.memories` (`source_session`). Capability facts in §4–§6 come from the current checkout `1f60a58` (`docs/CAOSCARE_PRODUCT_BASELINE.md`, `docs/ROOM214_SELF_CODE_INSPECTION.md`, `backend/aria_guidance_profiles.py`, `docs/PROJECT_STATE.md`). Author: Claude Code (Fable 5.1), read-only, 2026-10-15 18:05 CDT.

## 9. After the acceptance session (preserved, outside the requested scope)

`rt_87no5md6_1792104271070` (17:44–17:49 CDT): order a pizza / contact businesses (I10), send a text message (I10), a small sandbox for Aria to make things for Michael (I11), and a repeat of the "don't recite what you can't do" irritation (I2). Aria said she could "note that as a capability people want" — she cannot yet (I6).

## 10. Stage 3 reconciliation (2026-10-15 19:05 CDT) — against source `1f60a58`, docs PR #170, queue #166, open PRs #146/#160/#161/#167/#170

| Idea | Class | Evidence |
|---|---|---|
| I1 read-only self-code | ALREADY BUILT | PR #169, live-accepted 17:33 CDT |
| I3 creator/owner persists | ALREADY BUILT | pinned `db.memories` facts 2026-10-15; "that's on record" in session rt_87no5md6 |
| I8 menu not on file | ALREADY BUILT (code) / DUPLICATE OF EXISTING QUEUE (content) | Aria information principle; menu data entry is Kitchen commissioning under CO-008 (#166) |
| I2 + U1 stop re-stating an acknowledged limit | PARTIALLY BUILT — and the built part is **not applied** | `concise_natural` profile exists (`backend/aria_guidance_profiles.py`, 36 lines) but the Room 214 resident record `res_2425767f4a51` has **no `aria_guidance_profile`**, so Michael's room runs the default `supportive_guided` profile; the 2026-10-13 PROJECT_STATE step "resolve Michael's exact resident record and save `concise_natural` with a receipt" was never done. No profile text addresses an acknowledged limit. Loops observed 15:18–15:21 and 17:48 CDT. |
| I6 "I'll note that for the team" | NEW (truth defect) | `realtime_self_knowledge.py` line 111 instructs exactly that sentence; no channel exists, so it over-promises inside the NEVER-over-promise rule |
| I5 builder note channel | NEW | owner intake exists GitHub → coordinator (`docs/OWNER_INTAKE.md`), nothing Aria → backlog; destination is an owner decision |
| I4 wake/mic owner exemption | PARTIALLY BUILT / CONFLICTS WITH CURRENT DIRECTION | wake and audio-path tuning remain PARKED (CURRENT_PRIORITY); not now |
| I7 AC protocol truth | PARTIALLY BUILT / DUPLICATE | known defect (Midea off-commands), climate "In development"; CO-008/#164 realism lane territory |
| I9 email assistant, I10 order/text, I11 sandbox | NEW / CONFLICTS WITH CURRENT DIRECTION | resident-facing truth rule forbids claiming outside actions; belongs to a #163 (unified Aria gateway) owner decision packet, not a side build |

### Recommended single bounded next task — `room214-owner-profile-truth-001` (awaiting owner approval; nothing started)

**Goal.** Make Room 214 Aria actually run the owner's concise profile and stop re-reciting a limit the owner has already acknowledged.

**Scope (two small parts, one PR):**
1. **Data, through existing governance:** set `aria_guidance_profile = concise_natural` on resident `res_2425767f4a51` via the existing owner-only resident update route (`backend/routes/residents.py`), which writes receipt `resident_aria_guidance_profile_updated` with before/after. Needs the owner's signed-in session or explicit approval for the coordinator to do it on his behalf.
2. **Prompt-only, platform-wide file, profile-scoped effect:** add one sentence to the `concise_natural` body in `backend/aria_guidance_profiles.py`: once the resident has acknowledged a limit, do not restate it; if they say they are changing it, acknowledge once ("not yet — I'll follow whatever you change") and move on. Extend `backend/tests/test_aria_guidance_profiles.py`; add a real-prompt test (pattern of `test_aria_rewake_continuity.py`) proving the Room 214 prompt carries `PROFILE: concise_natural` and the new sentence.

**Acceptance.** (a) `GET /api/residents/res_2425767f4a51` → `concise_natural`, receipt present; (b) backend gate + the two tests; (c) guarded dev load; (d) live: Michael replays the 15:18 exchange ("you don't have it yet, I'm about to change it") — transcript shows one acknowledgement and no repeated boundary recital; "Can you change your code?" still answered No (self-code contract unchanged).

**Non-overlap.** Touches one 36-line prompt module, one test file and one resident record; no simulator, department, dashboard, #153 or CO-008 files; does not change wake, memory, tools, or the self-code gate. Second candidate, not bundled: `aria-self-knowledge-truth-001` — replace the "I'll let the team know you asked" sentence with a truthful one until a builder-note channel exists (I6).
