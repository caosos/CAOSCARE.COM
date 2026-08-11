# CAOSCare Progress Handoff — August 11, 2026

## Purpose

This document is a full handoff of the most recent CAOSCare work session and the product decisions that followed it. It is intended to let Claude Code, Claude Online, ChatGPT, developers, operators, and other collaborators re-enter the project without reconstructing the session from conversation history.

This report deliberately distinguishes:

- **PUSHED / VERIFIED** — visible in GitHub history or otherwise independently verified.
- **REPORTED LOCAL** — reported by the active Claude Code working session but not independently confirmed here as pushed to `main` at the time this report was created.
- **PLANNED / DIRECTION** — product or architecture decisions, not implementation claims.

At the time this report was prepared, the latest pushed CAOSCare code commit independently visible before this report was:

`3a4bd7f` — **Fix transcript-labeling bug; prove faucet-leak maintenance request works end-to-end**

This report commit does **not** mean every newer locally reported implementation described below has been pushed. Verify the repository and runtime before claiming deployment state.

---

# 1. Core CAOSCare model

CAOSCare is not simply a conversational assistant.

The operating loop is:

**context → memory → governance → action → receipt → learning**

Core phrase:

> **Aria speaks. CAOS routes.**

Aria is the human-facing conversational identity.

CAOSCare is the operating layer underneath her:

- identity
- context
- memory
- authority
- capability state
- tools
- actions
- verification
- receipts
- staff workflows
- building systems

The model/provider is replaceable. Identity, operational truth, memory, authority, action history, and receipts belong to CAOSCare.

---

# 2. Resident experience direction

## PLANNED / DIRECTION

The resident experience is **voice first**.

The resident should not have to learn departments, application navigation, menus, task categories, or a complicated dashboard.

The desired resident interaction is simply:

- “My faucet is leaking.”
- “I need to talk to my nurse.”
- “Can you contact the front desk?”
- “What’s for supper?”
- “Did anyone see my request?”
- “I need a ride to the pharmacy Thursday.”

Aria handles the conversation. CAOSCare handles the complexity.

The current browser/kiosk remains a **development and acceptance-test surface**, not the intended finished resident UI.

---

# 3. Operator / switchboard metaphor

## PLANNED / DIRECTION

A major design clarification from this work period:

> **Aria is the operator. CAOS is the switchboard.**

The resident-facing mental model is the old telephone operator / 411 model:

1. Pick up.
2. Say what you need.
3. The operator understands.
4. The switchboard routes it.
5. The right person or system responds.

The resident does not learn the organizational structure behind the request.

This also provides a much clearer explanation of the product than “an AI voice system.” The intelligence can remain largely invisible while the resident experiences a familiar human-style help line.

---

# 4. Handset / “Batphone” interface

## PLANNED / DIRECTION

A physical old-school telephone handset is now a strong prototype direction.

The interaction contract should remain extremely simple:

**lift handset → Aria session starts**

**talk naturally → CAOS routes**

**hang up → session ends**

Important design rule:

Do **not** turn the handset into an IVR or phone tree.

No “press 1 for nursing.”
No department menus.
No resident software-learning burden.

The handset is intended to exploit decades of resident muscle memory. Nostalgia is useful, but the deeper value is interaction familiarity.

The handset should be an optional deliberate/private-feeling entry point. The resident may still be able to talk to Aria in the room without physically picking it up.

Internal prototype nickname: **Batphone**.

The first physical prototype can be minimal:

- handset shell
- speaker
- microphone
- hook switch
- connection to the room node

Do not build rotary-dial shortcut complexity first.

---

# 5. Per-room mailbox / answering-machine model

## PLANNED / DIRECTION

The same familiar-object strategy extends naturally to messages.

Each resident room should eventually have its own governed mailbox.

Example:

Resident picks up and Aria can truthfully say:

> “You have three messages.”

Messages could come from authorized sources such as:

- nursing
- maintenance
- physical therapy
- front desk
- approved family contacts
- other facility staff

Truth requirements:

- real message count
- real sender attribution
- real read/unread state
- real timing when known
- no invented acknowledgment or arrival state

This mailbox is a natural return path for the larger bidirectional communication system.

---

# 6. Terminal 8 operational foundation

## PUSHED / VERIFIED

Terminal 8 established the beginning of CAOSCare as an actual facility operating layer.

Rather than creating parallel databases for every new request type, the existing `StaffTask` system was extended where appropriate.

The existing emergency `Alert` path remains separate and emergency-specific.

A generic `Receipt` foundation was introduced so operational truth can be observed consistently.

### StaffTask / resident request expansion

The request foundation now includes or supports concepts such as:

- category
- priority
- source
- visibility role
- resident words
- conversation session linkage
- acknowledgment
- assignment
- status

Resident request categories include:

- nursing
- maintenance
- kitchen
- front desk
- family
- complaint

### Receipt foundation

Meaningful actions can now be linked to receipts rather than relying on conversational claims.

Critical state distinction:

**created/sent ≠ acknowledged ≠ assigned ≠ completed**

Aria must only report the state that actually exists.

---

# 7. Department / role visibility

## PUSHED / VERIFIED FOUNDATION

Department-aware visibility was added to the task/request flow.

The goal is that auditability does not imply universal readability.

Examples:

- nursing sees nursing-authorized information
- maintenance sees maintenance-relevant operational information
- kitchen sees kitchen-relevant operational information
- family visibility is separately governed
- owner/admin may have broader operational visibility

Multi-user/multi-department production acceptance still requires broader real staff-account testing.

---

# 8. Resident request tools

## PUSHED / VERIFIED FOUNDATION

Aria gained operational tools including:

- `request_staff_help`
- `check_request_status`

The tool descriptions and backend behavior are intended to preserve truthful state reporting.

Good:

> “I sent the maintenance request.”

Not acceptable without evidence:

> “Maintenance is on the way.”

A request being created does not prove that a staff member acknowledged or accepted it.

---

# 9. Resident conversation / request viewing

## PUSHED / VERIFIED

Before building another resident conversation viewer, the existing resident Memory dialog was inspected.

An existing Conversation view already existed.

Instead of duplicating it, the request system was connected to that existing view, including a resident Requests view/tab using the canonical task data.

The desired traceability is:

**conversation → tool/action → request → receipt → status**

Conversation transcripts, operational receipts, and long-term personal memory remain separate concepts even where linked.

---

# 10. Realtime / WebRTC fixes from the same work period

## PUSHED / VERIFIED

Several real failures were discovered by exercising the actual Realtime path rather than trusting source inspection alone.

### A. `/negotiate` session routing bug

The intended ephemeral Realtime session was being minted correctly, but the live browser negotiation path could create/use a different generic session.

The negotiate path was repaired to use the intended ephemeral Realtime session.

### B. `session.update` API drift

A real data-channel/WebRTC test exposed multiple current API mismatches:

1. `session.type = "realtime"` is required.
2. voice moved under `session.audio.output.voice`.
3. input transcription moved under `session.audio.input.transcription`.
4. turn detection moved under `session.audio.input.turn_detection`.
5. obsolete `temperature` was removed from `session.update` rather than relocated by guesswork.

After repair, full Realtime/WebRTC tests produced clean session updates with real tools present.

### C. transcript event-name drift

The UI listened for:

`response.audio_transcript.done`

while the current Realtime API emits:

`response.output_audio_transcript.done`

This caused Aria’s spoken transcript turns not to land in UI transcript state correctly.

The event name was corrected.

---

# 11. Faucet maintenance acceptance path

## PUSHED / VERIFIED VIA FULL WEBRTC REPLAY

The phrase:

> “My faucet is leaking.”

was replayed through a full real WebRTC flow.

Observed outcome:

1. Aria recognized a maintenance need.
2. Aria selected `request_staff_help`.
3. The category was maintenance.
4. A real backend request was dispatched.
5. A real `StaffTask` was created.
6. A real linked `Receipt` was created.
7. The real tool result was sent back into the conversation.
8. Aria truthfully stated that the request had been sent.

The test task/receipt was later removed.

This proved the backend/protocol/action design.

A complete human microphone/browser acceptance remains a stricter final bar for any path that has only been protocol-replayed.

---

# 12. Browser-only `sessionIdRef` bug

## REPORTED LOCAL

After the pushed faucet/WebRTC replay, the active Claude Code session reported finding another issue that could only occur in the real frontend JavaScript path.

Reported cause:

`executeTool()` in `frontend/src/lib/useRealtimeVoice.js` lived outside the React hook but referenced `sessionIdRef.current`, even though `sessionIdRef` existed only inside the hook.

That could produce:

`ReferenceError: sessionIdRef is not defined`

before `fetch()` occurred.

This explains a pattern where:

- no backend request appeared
- no HTTP status existed
- the frontend returned a generic tool failure
- protocol-faithful Python/WebRTC replay did not catch the JavaScript scope error

Reported fix:

Thread `session_id` through the normal execution context just like resident ID, room, kiosk ID, etc.

Claude Code reported a clean browser page afterward, but the human microphone test remained the authoritative final acceptance at that point.

Verify current `main` before treating this as pushed.

---

# 13. Menu lane

## REPORTED LOCAL — BACKEND/API ACCEPTANCE REPORTED

The menu lane was reported built and acceptance-tested through its internal development path.

Target architecture:

**email/source → parse once → structured draft → staff approval → live menu → Aria reads approved truth**

Reported implemented behavior:

- development/test ingestion path
- email-ingestion adapter boundary
- parse into structured draft
- approval gate
- approved/live menu becomes Aria’s resident-facing reference
- corrected menu supersedes the old version
- supersession gap was discovered during testing and fixed before completion

Aria should answer phrases such as:

- “What’s for breakfast?”
- “What’s for lunch?”
- “What are we having for supper?”
- “What’s for dinner tonight?”

only from the current approved structured menu.

If no approved menu exists, Aria should say so rather than guessing.

### Important gap

A real external mailbox/polling mechanism is still unresolved.

Therefore:

- internal menu ingestion logic may be functional
- real mailbox receipt is **not yet proven**

Email remains a delivery/provenance adapter, not the menu database.

---

# 14. Transportation pilot

## REPORTED LOCAL — BACKEND/API ACCEPTANCE REPORTED

A substantial transportation simulation was reported completed.

### Two-week schedule

The pilot includes approximately two weeks of transportation availability during a normal bus operating window of roughly:

**8:00 AM → 4:00 PM**

### Synthetic resident/node activity

Five clearly synthetic TEST rooms/nodes were used to exercise concurrent facility activity.

### Request lifecycle

Reported lifecycle support includes:

- request
- change
- cancel
- complete

Future time semantics were added so language such as:

> “I need a ride Thursday.”

or:

> “Tomorrow at 10.”

is not flattened into an immediate request.

A shared `requested_for` / preferred-time concept is strategically useful for both transportation and later nursing workflows.

### Concurrency acceptance

A real concurrency test reportedly fired two residents at the same final available slot simultaneously.

Result:

Only one could win/confirm the slot.

This is an important operational truth rule:

**availability read ≠ confirmed booking**

The system must not tell two residents they both own the same slot.

### Daily transportation report

A daily operations report was reported built and reconciled.

Reported example reconciliation:

- 7 inbound requests
- 13 outbound/actions
- counts cross-checked correctly

The report is intended to answer:

- What requests came in?
- Who requested them?
- What was accepted/booked?
- What changed?
- What was cancelled?
- What was completed?
- What remains open?
- What requires attention?

### Timezone bug found through real data

The first report implementation reportedly compared UTC timestamps directly against facility-local calendar dates.

That produced zero results against known data.

Because the report was tested against real seeded development records, the bug was discovered and corrected.

This reinforces the project rule:

> **Code is not proof. Observable behavior is proof.**

### Seeded test data

The active Claude Code session intentionally left synthetic TEST data in the development environment so Admin → Transportation / Menu / Schedule could be inspected visually.

### Important gap

Real Outlook/calendar synchronization is not yet built.

Transportation currently uses an internal schedule according to the last report.

External calendar integration is the next adapter layer, not something that should be claimed as already live.

---

# 15. Email/calendar adapter rule

## ARCHITECTURE DECISION

CAOSCare remains the source of truth.

Email and calendar are adapters.

For requests, CAOSCare owns:

- request
- status
- thread
- assignment
- acknowledgment
- receipts
- history

For menus, CAOSCare owns the approved structured menu state.

For transportation, CAOSCare owns the request/receipt truth even when an external calendar becomes a schedule adapter.

Do not bind core domain semantics to Outlook, Gmail, or any one provider.

---

# 16. Pre-request verification / dedupe direction

## PLANNED / DIRECTION

Before blindly creating a second request, CAOSCare should check whether a relevant open request already exists.

Example:

1. “My faucet is leaking.”
2. “My faucet is still leaking.”
3. “Nobody fixed the faucet.”

Those may represent one unresolved operational issue, not three independent work orders.

However, repeated resident communication must not be silently discarded.

A repeat can mean:

- follow-up
- worsening issue
- increased urgency
- cancellation/change
- resident believes nobody responded

Desired behavior:

- find relevant open request
- preserve repeated resident words/history
- update or append appropriately
- escalate/raise priority under policy when warranted
- avoid blind duplicate tickets

A deliberate clinical-vs-convenience dedupe/escalation policy is still needed.

---

# 17. Bidirectional resident ↔ staff communication

## PLANNED / DIRECTION

The larger goal is not “submit a ticket and hope.”

The desired loop is:

**resident speaks → Aria understands → CAOS checks current state → request/thread is created or updated → department is notified → staff responds → reply returns into the governed thread → Aria relays the real response**

This should eventually support:

- nursing
- doctors/clinical staff
- maintenance
- front desk
- family-authorized communication
- transportation
- kitchen/meal information

The system should preserve one canonical governed thread where possible instead of creating parallel disconnected messaging systems.

---

# 18. Nursing / clinical communication direction

## PLANNED / DIRECTION

Routine nursing communication should stay separate from emergency alerts.

Examples:

- “I want to talk to my nurse.”
- “Tell the nurse the pain is worse today.”
- “I want to talk to my nurse tomorrow.”

Future-time semantics matter.

“Tomorrow” must not become “now.”

The shared requested-for/preferred-time field used in transportation should be reusable here where appropriate.

Aria does not gain autonomous clinical authority. The system helps communicate, organize, retrieve authorized information, maintain continuity, and report real state.

---

# 19. Front desk direction

## PLANNED / DIRECTION

Front desk should initially reuse the same request/receipt architecture.

Examples:

- “Can you contact the front desk?”
- “Ask the front desk to call me.”
- “Did they see my request?”

Initial implementation should favor a real queue/callback request rather than prematurely building a full telephony platform.

Later room-to-front-desk communication should account for:

- station identity
- availability/presence
- queue
- priority
- acceptance
- callback
- missed state
- receipts

Do not design a system where many residents blindly ring one endpoint simultaneously.

---

# 20. Emergency separation

## EXISTING PRINCIPLE

Emergency remains distinct.

A physical pendant/emergency mechanism should drive emergency behavior.

The existing red “Call for Help” screen control is a development/test interface.

Ordinary requests such as:

- routine nurse communication
- leaking faucet
- meal question
- front desk callback
- transportation request

should not be promoted to emergency Alerts unless the situation itself is actually an emergency.

---

# 21. Realtime conversational regression baseline

## PUSHED / VERIFIED

A successful real Aria conversation established an important regression baseline.

Aria:

- knew her identity
- did not fabricate contacting nursing
- handled legitimate sensitive adult-life/body-image/incontinence topics respectfully
- maintained useful conversational context

Do not “fix” legitimate mature conversation out of the system.

Truth and clinical-authority boundaries should be preserved without turning Aria into a prohibition-heavy or evasive system.

---

# 22. Sensory truth discipline

## EXISTING PRINCIPLE

Aria must not claim to perceive something she cannot actually perceive.

Never claim current vision without verified visual input.

Never infer:

- “I can see you.”
- “I see the cup.”
- “You’re sitting at the desk.”

without real current image/camera provenance.

Similarly:

- tool schema ≠ verified control
- request sent ≠ staff coming
- email sent ≠ recipient read it
- open calendar slot ≠ resident owns it
- notification delivered ≠ acknowledgment

Warmth and conversational humanity do not require false operational certainty.

---

# 23. Code modularity rule

## ESTABLISHED ENGINEERING RULE

Hand-written production files should generally remain below the established ~400-line ceiling/review gate.

This does not apply to:

- documentation
- reports
- generated artifacts
- static data

Do not begin a broad legacy refactoring project solely to satisfy line counts.

Instead:

- keep new code modular
- do not make giant files worse
- when actively changing an oversized area, extract a clean cohesive responsibility
- split by domain/responsibility, not arbitrary line chopping

Earlier Realtime backend work followed this approach.

The active Claude Code session also reported splitting `realtime_tools.py` and `useRealtimeVoice.js` before they grew further beyond the cap; verify current repository state before treating those newer splits as pushed.

---

# 24. Browser / UI verification discipline

## ESTABLISHED PROCESS RULE

A recurring lesson from this work period:

> **Code is not proof of user experience.**

For UI work, prefer:

1. open the real page
2. interact with the actual control
3. observe network/console behavior
4. inspect the visible state
5. compare expected vs actual behavior

The browser extension timed out on several later calls during the recent session.

The active Claude Code session correctly stopped retrying and labeled those surfaces:

**code/backend verified but not visually re-confirmed**

rather than pretending to have seen a successful render.

This distinction should be preserved.

---

# 25. Current open gaps

The following were still open at the end of the most recent reported work:

1. **Human microphone acceptance** for the newer transportation/menu resident voice paths.
2. **Human microphone acceptance** of the real browser request path after the reported `sessionIdRef` fix.
3. **Push/verify all newer local Claude Code changes** beyond `3a4bd7f`.
4. **Real inbound mailbox mechanism** for menu/email lanes.
5. **Real Outlook/calendar adapter** for transportation.
6. **Bidirectional nursing/staff replies** into the resident communication thread/mailbox.
7. **Front-desk queue/callback workflow**.
8. **Family authorization/visibility specifics**.
9. **Per-room mailbox/message delivery implementation**.
10. **Open-loop persistence and lifelong memory continuity**.
11. **Physical handset/Batphone prototype** once a test room/hardware target is chosen.
12. **Visual re-confirmation** of Admin Transportation/Menu/Schedule surfaces where browser extension timeout prevented final inspection.

---

# 26. Recommended immediate sequence

The next safe sequence is:

### Step 1 — verify current repository state

Check whether the newer local Claude Code work has been committed and pushed.

Do not assume a local working tree equals GitHub `main`.

### Step 2 — inspect seeded Admin data

Review the intentionally seeded development data in:

- Admin → Schedule
- Admin → Menu
- Admin → Transportation

Confirm rendered state when browser access is functioning.

### Step 3 — human voice transportation acceptance

Use the actual resident/browser microphone path.

Example:

> “I need a ride to the pharmacy tomorrow at 10.”

Acceptance requires:

- correct interpretation
- actual tool execution
- real backend state change
- truthful booking/request language
- receipt where required
- status query works afterward

### Step 4 — menu voice acceptance

Ask:

> “What’s for supper?”

Aria must answer only from the current approved structured menu.

### Step 5 — external adapters

After internal truth paths are accepted:

- real mailbox ingestion
- Outlook/calendar synchronization

Do not invert this order and build provider plumbing before proving the canonical internal state works.

### Step 6 — bidirectional communication

Continue toward:

- nurse/staff replies
- resident mailbox
- front-desk callback/queue
- family-authorized messaging

---

# 27. What not to do next

Do **not**:

- restart Terminal 8 from scratch
- create duplicate request databases without necessity
- build a resident dashboard full of controls
- turn the Batphone into an IVR
- bind the domain model to email or Outlook
- claim external integrations that are not actually configured
- flatten future-time language such as “tomorrow” into “now”
- claim a ride is booked merely because a slot looked available
- expose unapproved menu drafts to residents
- silently discard repeated requests
- let Aria claim staff acknowledgment that does not exist
- let Aria claim sensory perception she does not have
- launch a broad refactoring project during focused operational work
- treat API/backend tests as complete proof of the rendered resident experience

---

# 28. Overall status

The project has moved materially beyond:

> “Aria can talk.”

It is becoming:

> **“Aria can participate in the actual operation of the resident’s environment, with CAOSCare preserving truth, state, permissions, receipts, and continuity underneath.”**

The recent work established or substantially advanced:

- Realtime reliability
- resident operational request routing
- truthful request receipts/status
- maintenance acceptance path
- resident request visibility
- menu ingestion/approval architecture
- menu truth retrieval
- transportation scheduling
- transportation lifecycle handling
- concurrency protection
- daily operational reporting
- time-zone-correct reporting
- modularity discipline
- browser/visual acceptance discipline
- operator/switchboard product metaphor
- handset/Batphone resident interface direction
- per-room answering-machine mailbox direction
- bidirectional staff/resident communication architecture

The system is still under active development, and several newer items remain locally reported rather than independently verified as pushed. Preserve that distinction.

---

# 29. Handoff instruction for the next agent/developer

Before making new changes:

1. Read this document.
2. Read `CLAUDE.md`, `AGENTS.md`, and the canonical CAOS/Aria/engineering documents.
3. Read `docs/TERMINAL_8_OPERATIONAL_LAYER.md`.
4. Inspect current Git history and working tree.
5. Distinguish pushed implementation from local reported work.
6. Run the exact resident-facing acceptance path before claiming completion.
7. Preserve the architectural direction and regression baselines above.

The priority remains:

**resident speaks → Aria understands → CAOS routes → action/request is real → receipt exists → appropriate people/systems receive it → response returns → resident gets truthful continuity**
