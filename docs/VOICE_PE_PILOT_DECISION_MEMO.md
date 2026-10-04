# Voice PE Pilot 1 — decision memo (2026-10-04)

Decision support only. Each item is a choice for Michael; nothing below is
decided or implemented by this memo.

- **Verified:** confirmed in this repository (branch `spike/voice-bridge` at
  `be011a8`) or in a named source.
- **Recommended:** the coordinator's recommendation.

Sources:

- `docs/VOICE_PE_EXTERNAL_COMPONENT_AUDIT.md` ("the audit");
- `docs/VOICE_PE_BRIDGE_INSTALL.md`;
- `docs/ROOM_ANNOUNCEMENT_CONTRACT.md`;
- `docs/SPEAKER_VERIFICATION_DESIGN.md`;
- `docs/CAOSCARE_PRIVACY_SAFETY_SECURITY_NORTH_STAR.md`;
- `docs/PROJECT_STATE.md`;
- the code paths named under each decision.

---

## 1. Pilot voice path

**Decision:** for Pilot 1, should the room voice run on:

- **(A)** custom Voice PE firmware that streams audio directly to a
  CAOSCare-owned realtime voice endpoint (speech-to-speech); or
- **(B)** the stock Home Assistant Assist path: wake word on the device,
  Home Assistant speech-to-text, CAOSCare as the conversation agent through
  the voice bridge, Home Assistant text-to-speech?

**Verified current state:**

- (B) is built on `spike/voice-bridge`:
  - the bridge;
  - the Home Assistant agent `integrations/home_assistant/custom_components/caoscare_conversation`;
  - device→room mapping, receipts, the admission and emergency paths;
  - load-tested with simulated providers.
- (B) is not installed in Home Assistant. Home Assistant has no STT/TTS
  engine yet, and no physical Voice PE test has been done
  (`VOICE_PE_BRIDGE_INSTALL.md` §9).
- (A) does not exist in CAOSCare.
- The external realtime stacks studied in the audit use unauthenticated or
  cleartext WebSocket transport and are rejected as-is (audit §6, §10).
- The "Hey Aria" wake-word models from the firmware lane are labelled
  **RESEARCH ONLY — NOT COMMERCIALLY RELEASABLE** (wake-lab
  `recommend_lab.py`, `LICENSE_STATUS`). That applies to either path.

**Recommended: (B) for Pilot 1.** Keep (A) as a later, separately approved
project.

**Strongest alternative:** (A), a CAOSCare-owned realtime endpoint with
`wss://`, per-device credentials, and the same tools and receipts as the
bridge.

| | |
|---|---|
| Benefits of (B) | Already built; encrypted device ↔ Home Assistant link; stock firmware; one CAOSCare decision path with receipts; testable now. |
| Trade-offs of (B) | Staged speech (no barge-in or natural overlap); slower turns; speech-to-text quality depends on Home Assistant's chosen engine. |
| Benefits of (A) | Natural timing, interruption and lower perceived latency. |
| Trade-offs of (A) | New firmware to maintain (GPLv3, see decision 6); security work on transport and device credentials; audio streamed to the cloud model; higher model cost; nothing built. |
| Effect on Pilot 1 | (B): next steps are Home Assistant setup and a physical test. (A): Pilot 1 slips until an endpoint and firmware exist. |
| Reversible | Choosing (B) now does not block (A) later: the bridge's tools, receipts and room mapping are reusable. |
| Expensive to reverse | Shipping custom firmware to many rooms (reflashing and support), and building operations around a cloud audio stream. |
| Evidence | Audit §1, §6, §9, §13 Q1; `VOICE_PE_BRIDGE_INSTALL.md`; `docs/reports/2026-10-04-voice-bridge-load-test.md`. |

**MICHAEL DECISION REQUIRED**

---

## 2. Room-speaking authority

**Decision:** who and what may make CAOSCare speak through a resident's room
device, across:

- staff roles;
- CAOSCare workflows;
- system events;
- approved family contacts?

**Verified current state** (`backend/routes/room_announcement_policy.py`,
slice 1, `80e5cab`; `ROOM_ANNOUNCEMENT_CONTRACT.md`):

- **Allowed:**
  - owner, admin and front desk, to any room in the community;
  - department staff, only for their own department's request and only in
    that request's room;
  - three named in-process workflows (`request_status_update`,
    `transport_update`, `staff_dispatch_update`), each with an origin record.
- **Refused, with a receipt:** family, anonymous callers, other roles, and
  emergency priority (no policy exists).
- **No quiet-hours policy exists.** Each announcement records it as
  `none_defined`.
- Nothing is tested on real hardware.

**Recommended:**

- Keep the slice-1 set for Pilot 1.
- Add family only after a separate approval of how a family contact is
  verified and limited (approved contacts, message length, hours,
  per-resident consent).
- Define quiet hours before any automated system announcement runs at night.

**Strongest alternative:** allow verified family contacts now, through a
staff-approved message queue (staff release each message).

| | |
|---|---|
| Benefits | Every room-speaking action has a known, authenticated actor and an origin record; no unsolicited voices in a resident's room. |
| Trade-offs | Families cannot reach the room by voice; staff relay instead. Night-time limits are unenforced until quiet hours are defined. |
| Effect on Pilot 1 | None blocking; announcements are optional to the pilot. |
| Reversible | The roles and workflow list are one policy module; widening later is a small change. |
| Expensive to reverse | Opening the room to external senders: once families expect it, withdrawing it is a trust and support cost. |
| Evidence | `ROOM_ANNOUNCEMENT_CONTRACT.md`; audit §8 and §13 Q2; `PROJECT_STATE.md` 2026-10-04 slice 1. |

**MICHAEL DECISION REQUIRED:**

- (a) staff roles;
- (b) system workflows;
- (c) family yes/no and conditions;
- (d) quiet-hours rule;
- (e) whether any emergency announcement exists.

---

## 3. Reminders and timers

**Decision:** who may create, change, cancel or complete a resident reminder
or timer: resident by voice, staff, family, or system?

**Verified current state** (`backend/routes/timers.py`):

| Action | Current behaviour |
|---|---|
| Create | One-shot timers, by the realtime room session's `set_timer` tool through an unauthenticated `POST /api/timers/public` (a room claim) |
| Change | Not possible: no update endpoint |
| Cancel | Any signed-in user can delete any timer: `DELETE /api/timers/{id}` has no role or room check |
| Complete | No "completed" or acknowledged state |
| Deliver | The kiosk polls for due timers |

- No receipts are written for timers (0 `create_receipt` calls).
- Recurring medication reminders are a separate admin-managed model
  (MedReminder).
- The voice bridge has no timer tool (audit §4).

**Recommended:**

- Residents may create, and cancel their own, simple timers by voice in
  their room.
- Staff (owner/admin/nursing for care reminders) may create, change and
  cancel for a resident.
- No family access in Pilot 1.
- Every create, change, cancel, fire and acknowledge writes a receipt.
- Deliver through the room-announcement path (audit slice 4).
- Medication timing stays with the staff-managed reminder, never set by
  voice alone.

**Strongest alternative:** staff-only reminders for Pilot 1, with no
resident-created timers.

| | |
|---|---|
| Benefits | Familiar resident convenience; care reminders stay staff-owned and auditable. |
| Trade-offs | Building and testing the receipts, permissions and delivery work; voice-created timers are room claims, not verified identity. |
| Effect on Pilot 1 | Not required for Pilot 1; the current gaps (no receipts, unscoped delete) remain until addressed. |
| Reversible | Who may create and cancel is a policy setting once receipts exist. |
| Expensive to reverse | Letting voice alone change medication-related timing; letting families schedule speech in rooms. |
| Evidence | `backend/routes/timers.py`; audit §8 (timers row), §11 slice 4, §13 Q3. |

**MICHAEL DECISION REQUIRED:**

- (a) is it in scope for Pilot 1;
- (b) who creates, changes, cancels and completes;
- (c) whether residents may set them by voice.

---

## 4. Audio and transcript handling

**Decision:** for each item, choose:

- raw room audio: transient processing only, or retained;
- whether text transcripts are stored, and for how long;
- whether diagnostic recordings are allowed;
- what consent is required;
- what retention periods apply.

**Verified current state:**

- **Voice bridge path (B):** CAOSCare receives text only. Speech-to-text
  runs in Home Assistant with an engine not yet chosen (local Whisper or a
  cloud engine; `VOICE_PE_BRIDGE_INSTALL.md` §5).
- **Stored text:**
  - each turn's utterance and reply are stored in `db.conversations`;
  - they are also stored in the voice-turn receipt evidence
    (`voice_bridge_receipts.py`).
- **No retention limit:** no TTL or retention period exists for
  conversations or receipts. The only TTL found is capacity samples
  (30 days).
- **Realtime room session:** audio streams to the cloud model; transcripts
  are stored.
- **Raw audio:** no raw-audio retention exists in CAOSCare. Room
  announcements involve none.
- **Policy rule:** "Do not retain raw audio/video unless required and
  authorized" (`CAOSCARE_PRIVACY_SAFETY_SECURITY_NORTH_STAR.md`).
- **No consent record** for voice transcripts was found.

**Recommended:**

- Raw audio: transient only, never stored, including no diagnostic
  recordings in Pilot 1.
- Prefer a local speech-to-text engine in Home Assistant, so room speech
  stays in the building.
- Store transcripts, because they are the evidence behind requests and
  receipts, with:
  - a defined retention period (proposal, for Michael to set: 90 days for
    conversation text; receipts kept per the receipt law);
  - resident/representative consent recorded at onboarding.

**Strongest alternative:** permit opt-in diagnostic recordings during the
pilot only, with a short retention (for example 14 days) and per-resident
written consent, to tune false wakes and speech recognition.

| | |
|---|---|
| Benefits | Least sensitive data; matches the existing privacy rule; receipts stay explainable. |
| Trade-offs | Harder to diagnose mis-hearing and false wakes; a local speech-to-text engine needs EliteDesk CPU (capacity monitor applies). |
| Effect on Pilot 1 | A consent step and a retention setting before residents use it; the speech-to-text engine choice is needed for Home Assistant setup. |
| Reversible | Retention periods and the speech-to-text engine are configuration. |
| Expensive to reverse | Any audio already sent to a third party or retained cannot be recalled; resident trust. |
| Evidence | `CAOSCARE_PRIVACY_SAFETY_SECURITY_NORTH_STAR.md`; `VOICE_PE_BRIDGE_INSTALL.md` §5–6; `voice_bridge_receipts.py`; audit §6.5–6.6. |

**MICHAEL DECISION REQUIRED:**

- (a) raw audio policy;
- (b) diagnostic recordings yes/no;
- (c) transcript retention period;
- (d) consent requirement;
- (e) local versus cloud speech-to-text.

---

## 5. Speaker recognition

**Decision:** may speaker recognition be used, and only as a
personalisation/context signal, or ever as identity or authorization?

**Verified current state:**

- Not implemented.
- `SPEAKER_VERIFICATION_DESIGN.md` (design only, 2026-09-24) records
  Michael's ratified boundary: speaker verification ≠ authentication.
- The audit rejected it as identity or authorization (§6.3, §10).
- No CAOSCare authorization uses voice.

**Recommended:**

- Not in Pilot 1.
- If later approved, personalisation/context only (for example greeting,
  likely speaker).
- It must **never** independently authenticate a person or authorize an
  action unless Michael later explicitly approves a proven method.

**Strongest alternative:** a limited personalisation trial after the pilot,
with enrolment consent, a stored-voiceprint policy, and no effect on any
permission.

| | |
|---|---|
| Benefits | No biometric data held; no risk of a voice being treated as proof. |
| Trade-offs | No per-person personalisation when several people share a room. |
| Effect on Pilot 1 | None. |
| Reversible | Adding personalisation later is additive. |
| Expensive to reverse | Collecting voiceprints (biometric data with consent and deletion duties); any workflow that comes to depend on voice as identity. |
| Evidence | `SPEAKER_VERIFICATION_DESIGN.md` §0; audit §6.3, §8, §13 Q5. |

**MICHAEL DECISION REQUIRED:**

- (a) exclude from Pilot 1;
- (b) if later, personalisation only;
- (c) confirm it never authenticates without a separately approved, proven
  method.

---

## 6. Firmware licensing

**Decision:** does Michael accept GPLv3 source-distribution obligations for
any custom Voice PE firmware CAOSCare ships, while keeping CAOSCare's
proprietary backend and business logic separate?

**Verified current state** (audit §2, §5):

- **Voice PE firmware:**
  - ESPHome licence: C/C++ under GPLv3, Python and YAML under MIT.
  - Sounds under CC BY 4.0.
  - Hardware under CERN-OHL-P.
- **Custom changes ship as GPLv3 code:** distributing a firmware binary with
  modified C++ (for example a custom `va_client`) means offering the
  corresponding source to recipients.
- **CAOSCare's backend is separate:** it is not part of the firmware and
  talks to it over a network protocol. AGPL projects were excluded from any
  incorporation.
- The current path (B) uses stock firmware plus a wake-word model; models
  are research-only today (decision 1).
- No legal review has been done.

**Recommended:**

- Accept the GPLv3 obligations for any shipped firmware: publish its
  source, including CAOSCare's firmware changes.
- Keep all CAOSCare business logic, workflows and data outside the firmware,
  in the separately licensed backend.
- Ship no firmware containing AGPL code or a model without a clear licence.
- Get a legal review before the first commercial shipment.

**Strongest alternative:** ship only stock, unmodified Nabu Casa firmware
(updates from the vendor), with only configuration and a licensed wake-word
model added. This minimises CAOSCare-owned firmware code; whether the
obligations change still needs legal confirmation.

| | |
|---|---|
| Benefits | Clear compliance; the firmware stays a thin device layer; no exposure of backend IP. |
| Trade-offs | Firmware changes become public; must keep source available for shipped versions. |
| Effect on Pilot 1 | Low for an internal pilot (no distribution to third parties). It becomes material once devices are delivered to communities. |
| Reversible | Until firmware is distributed. |
| Expensive to reverse | After shipping: the source-offer duty attaches to each distributed version. |
| Evidence | Audit §2, §5, §13 Q6; firmware `LICENSE` files cited there. |

**MICHAEL DECISION REQUIRED:**

- (a) accept GPLv3 obligations for shipped custom firmware;
- (b) confirm backend/business-logic separation as policy;
- (c) whether a legal review is required before the first shipment.

---

## Summary of decisions awaiting Michael

| # | Decision | Recommendation |
|---|---|---|
| 1 | Pilot voice path | Stock HA Assist + CAOSCare bridge for Pilot 1; realtime later |
| 2 | Room-speaking authority | Slice-1 roles and workflows; no family yet; define quiet hours |
| 3 | Reminders/timers | Resident voice create/cancel own; staff manage; receipts; no family; medication timing staff-only |
| 4 | Audio and transcripts | No raw audio; local speech-to-text; transcripts kept with a set retention and recorded consent |
| 5 | Speaker recognition | Not in Pilot 1; later personalisation only; never authentication without a proven, approved method |
| 6 | Firmware licensing | Accept GPLv3 for shipped firmware; keep business logic in the backend; legal review before shipping |
