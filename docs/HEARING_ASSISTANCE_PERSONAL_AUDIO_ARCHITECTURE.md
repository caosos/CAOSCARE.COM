# Hearing Assistance & Personal Audio — Architecture

**Status:** RESEARCH + PROPOSED ARCHITECTURE. Nothing in this document is implemented. No physical hearing-aid test has been run.
**Lane:** Round 5, Agent Six, RQ-009. Branch `research/hearing-assistance-audio`, cut from `origin/integration/2026-09-27` @ `18405b2` (the assignment named `1118baa`; integration had moved one coordinator commit, `18405b2`, by the time this branch was cut).
**Research date:** 2026-10-04. Every claim about Apple, Google, the Bluetooth SIG or a manufacturer cites a source in §14, with the date it was accessed. Where no primary source was found, this document says so.
**Relationship to other records:** `docs/ROOM_AUDIO_ARCHITECTURE.md` stays the canonical record for room audio. The Voice PE is the room endpoint, there is one capture point and one AEC path per room, and the handset is the guaranteed duplex fallback. This document adds an **optional personal-audio layer** on top of that record and changes none of its decisions.

---

## 1. Executive conclusion

1. **The room path (Voice PE microphone + Voice PE speaker) remains the universal default.** Hearing aids are an optional *personal output endpoint*, reached **through the resident's own phone**, which keeps its manufacturer-intended pairing. CAOSCare infrastructure should **never pair directly with a resident's hearing aids**. Section 6.1 gives the reasons.
2. **Hearing-aid output is broadly achievable today.** Every major 2024–2026 family streams from iPhone (MFi). On Android it streams over ASHA, LE Audio (HAP) or Bluetooth Classic, depending on the model and the phone.
3. **Hearing-aid *microphone* capture by a normal app is NOT something CAOSCare can rely on.**
   - **ASHA is output-only by specification.** During calls the phone's own microphones carry the voice.
   - On iPhone, Apple documents bidirectional MFi as "hands-free" for calls. Apple's own developer docs describe the `bluetoothLE` port as **an output**. We found no Apple documentation that a third-party app can select an MFi hearing-aid microphone as input.
   - On Android, LE Audio hearing aids *can* provide a microphone. Google documents app routing through `setCommunicationDevice()`, but this needs an LE Audio phone, an LE Audio aid and Android 13/14+.
   - Bluetooth Classic aids (Phonak, Signia BCT) expose HFP, so the aid's microphone works for calls on any phone.

   **Mode C is therefore "per verified combination only".** It is never a default and never a sales claim.
4. **Recommended default for a hearing-aid user: Mode B-room.** The **Voice PE hears** the resident and **Aria's reply streams to the hearing aids** through the phone. Room fallback is automatic. This keeps the proven far-field microphone, keeps the room AEC path intact (in-ear playback does not reach the Voice PE microphone), and needs no hearing-aid microphone.
5. **Dual output (Mode D) is not recommended as a conversational default.** Bluetooth streaming adds latency, and ASHA's own documented buffer is in the order of 160 ms. That latency against the room speaker produces a doubled, echo-like signal for the wearer. Mode D is acceptable only for short announcements or alarms, where the room speaker guarantees delivery.
6. **The highest-value hearing-aid path for *telephone calls* is not Bluetooth at all.** It is a **hearing-aid-compatible (HAC, telecoil-coupled) corded handset**, the D5 device that Pilot 1 already plans. Calls placed to a resident's own mobile number also use the phone's native, manufacturer-supported hearing-aid call path.
7. **Auracast is a common-area and TV technology, not the personal Aria channel today.** iPhone has no Apple-documented native Auracast support (§3.6). Widex announces support only for 2026. Auracast is receive-only. Treat it as a **future common-area announcement and TV path**. Do not plan private Aria audio on it.
8. **Telecoil is worth documenting and staying compatible with.** It needs no pairing and no phone, and it is required/standard in loop-equipped venues. CAOSCare should require HAC/T-coil-rated handsets and note loop support in common rooms. It should not build telecoil-specific software.

---

## 2. Current standards landscape

| Technology | Who defines it | Direction | Phone support | What CAOSCare can rely on |
|---|---|---|---|---|
| **MFi hearing devices** (Apple proprietary, BLE-based) | Apple | Unidirectional on iPhone 4s+ (iOS 15.2+). **Bidirectional "hands-free"** on iPhone 11+ (iOS 15.2+) with supporting aids [A2] | iPhone/iPad/Mac/Vision Pro | Output from any app follows the OS route. The aid microphone is documented for calls only, not for app input (§3). |
| **ASHA** (Audio Streaming for Hearing Aids) | Google/AOSP | **Output only.** "There is no audio backlink… During a phone call the central microphones are used for voice input." [G1] | Android, manufacturer-dependent | Output. **Never** the aid microphone. |
| **Bluetooth LE Audio** (BAP/CAP, LC3) | Bluetooth SIG | Bidirectional capable | Android 13+ built-in; Android 14 routing changes [G3][G4] | Output, plus microphone on supported phone + aid pairs |
| **HAP** (Hearing Access Profile v1.0, adopted 2022-06-07) | Bluetooth SIG | Roles: Hearing Aid, Unicast Client, Remote Controller, Immediate Alert Client. An aid that supports the BAP Audio Source role **must** expose the Microphone Input Control Service "for telephone functionality". Defines **presets** (programs) with Active Preset notifications, and binaural sets via CSIP [B1] | Pixel lists ASHA + HAP [G2] | The standard path for future bidirectional aids. Microphone support is optional per aid (Audio Source role). |
| **TMAP / CCP / VCP / MICP** | Bluetooth SIG | Telephony, call control, volume and mic mute (dependencies of HAP) [B1] | OS-owned | The OS uses these. CAOSCare does not speak them. |
| **Bluetooth Classic HFP/A2DP** | Bluetooth SIG | HFP is bidirectional (aid mic for calls). A2DP is output | Any phone | Phonak and Signia BCT families use it [M1][M5]. Universal, but the phone treats the aid as a headset. |
| **Auracast** (LE Audio broadcast) | Bluetooth SIG | **Broadcast, receive-only.** Optional encrypted broadcast code for private listening [B3] | Android 15/16 on selected phones [M2]. iPhone: no Apple-documented native support (§3.6) | Future common-area/TV assistive listening |
| **Telecoil / induction loop** | IEC 60118-4 (loops), FCC HAC rules (handsets) | Receive-only, magnetic | No phone needed | Universal legacy path. Required in HAC-rated handsets (T-rating) [L1][L2] |

**What CAOSCare can reasonably rely on today:** *output* to hearing aids through the resident's phone. *Input* only from the Voice PE, the handset, or the phone's built-in microphone. Everything else is a verified exception.

---

## 3. Apple path

### 3.1 Documented facts
- **System requirements** [A2]:
  - **Unidirectional:** iPhone 4s or later, iOS 15.2 or later.
  - **Bidirectional:** iPhone 11 or later, iOS 15.2 or later.
  - Apple says bidirectional streaming "allows you to talk hands-free".
- **Brands Apple lists for bidirectional:** about 45, including Oticon, ReSound, Jabra, Starkey, Signia, Rexton, Philips, Bernafon, Beltone, Audibel and others [A2]. **Phonak and Widex are not on that bidirectional list.** Phonak uses Bluetooth Classic HFP instead [M1]. Widex documents hands-free only on Allure RIC R D with iPhone [M6].
- **Audio routing is a user/OS setting, not an app setting** [A3][A4]:
  - The user chooses whether call audio and media audio go to the hearing device, and whether ringtones play there.
  - *Settings > Accessibility > Call Audio Routing* offers Automatic / Speaker / hearing devices.
- **Live Listen** turns the iPhone into a remote microphone that streams *to* the aids [A1]. This is the opposite direction to what Aria needs, but it is relevant (§3.5).

### 3.2 What an app can do
- **Output.** An app plays through whatever route iOS chooses. For an MFi hearing device, AVAudioSession reports a `bluetoothLE` port. Apple's own definition of that port is "**An output** to a Bluetooth Low Energy (LE) device." [A5] In contrast, `bluetoothHFP` is "An I/O connection" [A5].
- **Input from the hearing-aid microphone.** We found **no Apple documentation** that a third-party app can choose an MFi hearing-aid microphone through `availableInputs`/`setPreferredInput`.
  - An Apple Developer Forums thread from June 2026 (unanswered, no Apple reply) reports that iOS couples input and output routes when MFi aids are involved: "making the MFi the output steals the input" [A6].
  - This is **secondary evidence, not proof**. It is a physical-test item (§12).
- **Web (Safari/WebRTC).** The current resident voice client uses `getUserMedia` with no `deviceId` and has no `setSinkId` (`ROOM_AUDIO_ARCHITECTURE.md`). A browser client on iPhone therefore inherits the OS route and cannot pick the hearing aid explicitly. This matches the "follow the OS route" posture recommended here.

### 3.3 Telephone calls on iPhone
- A cellular or FaceTime call uses the OS call route.
- With a bidirectional aid on iPhone 11+, the call can be hands-free (aid microphone).
- Otherwise the iPhone microphone carries the voice and the aids carry the far end.
- CAOSCare does not control this, and it does not need to.

### 3.4 Limitations by model
Whether a resident gets bidirectional calling depends on all of these together:
- the aid model
- the aid firmware (Signia AX, for example, needs firmware 20.11.509.2+ [M5])
- the iPhone generation (11+)
- the iOS version

A brand name alone proves nothing.

### 3.5 Live Listen caution
If Live Listen is on, the aids receive the iPhone microphone. A resident may hear Aria twice: once streamed, once through the phone microphone picking up the room speaker. **Note for HA-12 testing.**

### 3.6 LE Audio / Auracast on iPhone
- Apple's hearing-device pages make no mention of LE Audio [A2].
- **No Apple primary source documents native Auracast support.** A vendor article dated 2025-09-03 states "iPhones don't yet support Auracast natively" [S2]. Hearing-aid apps (GN/ReSound, Starkey) offer an "Auracast assistant" that lets the *aid* join broadcasts [M3][M4].
- **Re-verify against current iOS release notes before any Auracast claim.**

---

## 4. Android path

### 4.1 Documented facts
- **ASHA** is a GATT service over L2CAP CoC, using G.722 at 16 kHz [G1].
  - It is **output-only**. During calls, the phone's microphones carry the voice [G1].
  - Binaural behaviour: "if a peripheral is missing, due to a monaural fit or a loss of connection, then the central mixes the left and right audio channel and transmits the audio to the remaining peripheral" [G1].
  - Latency comes from an elastic buffer: 8 packets × a 20 ms connection interval ≈ 160 ms network delay [G1].
- **LE Audio / HAP**: "Android 13 (API level 33) includes built-in support for LEA". "Hearing aids that support BLE Audio can now use the microphone, allowing users to continually use their hearing aids for a call." [G3]
- **Android 14 routing change**: "hearing aids are now presented as one of the available audio output options, requiring explicit selection by the user". Before this, audio "would always default to hearing aids" [G4]. VoIP apps must use `AudioManager.setCommunicationDevice()` (API 31+) [G4].
- **Device types** [G5]:
  - `TYPE_HEARING_AID` (ASHA) is "a device type describing a Hearing Aid".
  - `TYPE_BLE_HEADSET` is "a Bluetooth Low Energy (BLE) audio headset or headphones".
  - LE Audio hearing aids generally appear as `TYPE_BLE_HEADSET`, not `TYPE_HEARING_AID`. **Physical-test item:** confirm how a given aid enumerates.
- **Pixel**: "Certain Pixel phones can stream audio… over… ASHA or… HAP." Pixel HAC tables list "BT: Yes (ASHA; HAP)" [G2]. Google advises users to check with their manufacturer, and notes that newer wireless technologies may not yet be tested [G2].

### 4.2 Manufacturer differences that matter
- **ASHA support is not universal.** Signia states: "Not all Android phones support the ASHA protocol as implementation depends on the phone's manufacturer" [M5].
- **LE Audio phone lists are short and explicit:**
  - ReSound lists Samsung Galaxy S23/S23+/S23 Ultra for hands-free [M3].
  - Widex lists Pixel 7 and newer (not 7a), Galaxy S23 and newer (not S23 FE), and Flip/Fold 4 and later, all on Android 14+ [M6].
  - Starkey requires Android 14+ and recommends 16+ [M4].
- **Accessory bridges exist for phones without LE Audio:** Oticon Easy LE Adapter, Starkey StarLink Edge LE Audio Adapter [M2][M4].

### 4.3 What an app can do
- **Output:** follows the OS. From Android 14 the app must explicitly select hearing aids with `setCommunicationDevice()` for communication audio [G4].
- **Input:** `setCommunicationDevice()` selects the device for "voice or video calls" [G3]. On an LE Audio aid that has a microphone, this is the documented route to the aid microphone. **On ASHA it is impossible** [G1].
- **Web (Chrome on Android):** `getUserMedia` follows the communication route. Whether Chrome's WebRTC path picks the LE Audio aid microphone automatically is **unknown** (§12).

---

## 5. Major hearing-aid ecosystem matrix (sample — not a support list)

Read every row as: "this manufacturer documents X under conditions Y". **No row means "works with CAOSCare".** CAOSCare support exists only per verified resident setup (HA-03…HA-06).

| Family (current, 2024–2026) | iPhone streaming | iPhone hands-free (aid mic) | Android streaming | Android hands-free (aid mic) | Auracast | Notes / dependencies | Src |
|---|---|---|---|---|---|---|---|
| **Phonak Audéo Infinio / Infinio Sphere** | Yes (Bluetooth Classic A2DP) | Yes (HFP), any Bluetooth phone | Yes (Classic) | Yes (HFP) | Phonak KB has an Auracast article. Model-level support not confirmed in this research | Classic Bluetooth = "universal". The phone sees one Classic entry plus two LE entries (app) [M1]. Not on Apple's MFi bidirectional list | M1, A2 |
| **Oticon Intent** (and 2025 update) | Yes (MFi) | Yes (MFi bidirectional) | Yes (ASHA or LE Audio) | **Only with an LE Audio phone**, or with the Easy LE Adapter | Yes, with Android 15+ on selected LE Audio phones | Two-way on Android needs LE Audio | M2 |
| **ReSound Vivia / Nexia / Savi** (Jabra Enhance is a GN sister brand — confirm separately) | Yes (MFi) | iPhone 11+ | Yes (ASHA / LE Audio) | LE Audio phone with Bluetooth 5.3+, e.g. Galaxy S23 family | Yes, "Auracast Assistant" in the Smart 3D app (v1.39), iPhone included | Auracast through the app, not the iOS OS | M3 |
| **Starkey Omega AI / Edge AI** | Yes (MFi), iOS 15+ | Yes | Yes (Android 14+; 16+ recommended) | Omega/Edge on LE Audio phones. Older Genesis/Evolv: no Android hands-free | Auracast assistant (Jan 2026) | StarLink Edge LE Audio Adapter for other phones | M4 |
| **Signia IX** | Yes (MFi) | iPhone 11+ | ASHA; LE Audio with firmware 25.5.972.3+ | LE Audio phone only | Not established here | Firmware-dependent | M5 |
| **Signia Pure Charge&Go BCT IX** | Yes (Bluetooth Classic) | Yes | Yes (Classic) | Yes. "HandsFree cannot be turned off" on Android | — | Classic = universal. The aid microphone is *forced* on Android calls | M5 |
| **Widex Allure RIC R D** | Yes (MFi), app needs iOS 17+ | **Yes, the only Widex model with iPhone 2-way** | ASHA (Android 11+) and LE Audio (Android 14+, listed phones) | Not documented | **Not yet.** "future software and app update in 2026" | Widex is not on Apple's bidirectional brand list | M6, A2 |

**What the matrix shows:**
- There are three different microphone stories: MFi (iPhone 11+), LE Audio (short Android list) and Bluetooth Classic HFP (any phone).
- ASHA-only Android setups never provide the aid microphone.
- CAOSCare cannot infer capability from brand. It must record the exact model, firmware/OS and a test result.

---

## 6. CAOSCare architecture recommendation

### 6.1 Should CAOSCare ever pair directly to hearing aids? **No.**
1. **The resident owns that pairing.** MFi and ASHA pairing is OS-mediated and tied to the resident's phone (MFi needs Apple hardware). A central server or a Voice PE cannot act as an MFi central device.
2. **Bilateral sets are coordinated sets.** HAP binaural sets use CSIP [B1], and Classic aids present multiple entries [M1]. A second central device competes for connection slots. Phonak, for example, documents up to 8 paired devices with 2 connected at once [M1]. Taking a slot can disconnect the resident's phone, which breaks their phone calls. That is a resident-harm risk.
3. **Range and topology.** The community server is central and has no per-apartment radio. This research found no documentation of the Voice PE acting as a Bluetooth hearing-aid central device, and no CAOSCare plan assigns it that role. Adding apartment BLE hardware contradicts the 2026-10-03 room decision (no per-apartment compute).
4. **Liability and fitting.** Program and preset control (HAP presets [B1]) belongs to the resident and the audiologist. CAOSCare must not change hearing-aid programs.

**The phone is the Bluetooth owner and bridge.** CAOSCare reaches hearing aids only by playing audio on a CAOSCare surface on the resident's phone, which the OS then routes.

### 6.2 Modes

| Mode | Input | Output | Default? | Verdict |
|---|---|---|---|---|
| **A — Universal room** | Voice PE | Voice PE speaker | **Yes, always available** | Required baseline. Works with no aids, telecoil aids, Bluetooth aids, or a dead phone. |
| **B-room — Personal output, room mic** | Voice PE | Phone → OS route → hearing aids | **Recommended for Bluetooth aid users** | Uses the proven far-field mic. In-ear output does not feed back into the Voice PE mic, so the room AEC stays clean. Needs a phone-side Aria audio surface (§11). |
| **B-phone — Personal output, phone mic** | Phone built-in mic | Phone → hearing aids | Optional (resident away from the Voice PE, inside the community) | Works for ASHA and MFi unidirectional aids. The phone mic is near-field when held. |
| **C — Bidirectional personal** | Hearing-aid mic via OS route | Hearing aids | **Never default. Per verified combination only** | Android LE Audio + `setCommunicationDevice()`, or Classic HFP, or MFi *if* §12 proves app access. Must pass HA-05 for *that* resident's exact setup. |
| **D — Dual output** | Voice PE | Voice PE speaker **and** aids | Announcements/alerts only | Bluetooth latency (ASHA ≈ 160 ms network buffer alone [G1]) against the room speaker gives a doubled signal. Aids also pick up the room speaker acoustically through their own mics. Not for conversation. |
| **E — Fallback** | Voice PE | Voice PE speaker | Automatic | Any personal-path failure reverts to Mode A without dropping the request (§7). |

### 6.3 Ownership boundaries (consistent with `ROOM_AUDIO_ARCHITECTURE.md`)
- **Conversation identity** stays one Aria session and one conversation history, whichever endpoint renders audio. The personal endpoint is a *render target*, not a second assistant.
- **Logical roles.** The four roles in `ROOM_AUDIO_ARCHITECTURE.md` (Aria playback, TV playback, resident capture, handset) gain one more: **personal playback**, meaning Aria playback routed to a resident-owned device. **Which physical device implements personal playback is the OS's decision**, not CAOSCare's.
- **Truth.** CAOSCare records *requested route*, *attempted route*, *confirmed delivery* and *fallback taken*. It never assumes that audio reached the aids. Delivery confirmation can come from the phone client's playback-start/ended events and its heartbeat. Whether the OS actually routed to the aids is reported only as far as the platform exposes the current route (iOS `currentRoute` output port type, Android communication device). Anything beyond that is recorded as `unknown`.

---

## 7. Input / output / fallback decision tree

```
Resident speaks (wake: "Hey Aria")
│
├─ INPUT
│   ├─ Voice PE hears wake + utterance ───────────────► use Voice PE (Mode A/B-room)   [default]
│   ├─ Resident on phone surface, Mode C verified for this
│   │   exact aid+phone+OS (HA-05 PASS) and route present ► hearing-aid mic via OS
│   ├─ Resident on phone surface, otherwise ───────────► phone built-in mic (B-phone)
│   └─ Handset lifted ─────────────────────────────────► handset (telephony path, D5)
│
├─ OUTPUT (decided per reply, in this order)
│   1. personal_audio_priority = off, OR no verified personal profile ─► room speaker
│   2. phone client online (heartbeat fresh) AND last route report shows a
│      hearing-device/BLE/HFP output AND resident preference = hearing aids
│         ─► send reply to phone client ─► OS routes to aids
│            ├─ playback-start ack within T_ack ─► record "personal delivered (route: X)"
│            └─ no ack / error / route changed to phone speaker
│                 ─► replay same reply on room speaker (Mode E), record fallback
│   3. preference = both AND message class ∈ {alert, announcement}  ─► Mode D
│   4. otherwise ─► room speaker
│
└─ INVARIANT: a resident request is never dropped because personal audio failed.
   The reply and any request it created are already committed server-side before
   rendering. Rendering failure triggers replay on the room speaker; it never
   rolls back the request.
```

`T_ack` and the heartbeat interval are **unknown until measured** (§12). The room replay will be audible to anyone in the room. That is the accepted cost of never losing a reply. The resident can choose to make their profile room-only (HA-11).

---

## 8. Resident profile proposal (NOT implemented)

Principle: store **device and preference facts needed to route audio**, not health data. No audiogram, no degree or type of hearing loss, no diagnosis, no audiologist notes. Collect with resident (or authorised representative) consent. Show the profile to staff only as routing needs require.

```yaml
hearing_assistance:
  enabled: false                      # bool; resident opted in to personal audio
  hearing_aid_make: null              # str, e.g. "Oticon"
  hearing_aid_model: null             # str, exact model as marketed, e.g. "Intent 1 miniRITE R"
  hearing_aid_firmware: null          # str|null; capability is firmware-gated (Signia AX/IX) — ADDED
  fitting: null                       # "left" | "right" | "bilateral"; routing only (monaural mix)
  telecoil_available: null            # bool|null; enables HAC handset / loop guidance — ADDED
  phone_platform: null                # "ios" | "android" | "none"
  phone_model: null                   # str
  os_version: null                    # str; capture date with it
  bluetooth_type: null                # "mfi" | "asha" | "le_audio" | "classic" | "none" | "unknown"
  streaming_supported: "unknown"      # "yes" | "no" | "unknown"   (tri-state, never assumed)
  bidirectional_microphone_supported: "unknown"   # manufacturer claim for this combo
  verified_by_test:                   # evidence, not a boolean
    output: null                      # {test_id: "HA-03", result: "pass", at: ISO8601, by: staff_id}
    microphone: null                  # {test_id: "HA-05", ...}
  preferred_input: "room"             # "room" | "phone" | "hearing_aid" (hearing_aid only if verified_by_test.microphone pass)
  preferred_output: "room"            # "room" | "hearing_aid" | "both_alerts_only"
  room_audio_fallback: true           # LOCKED true; not resident-editable (Mode E invariant)
  personal_audio_priority: "off"      # "off" | "prefer_personal" — personal attempted first, room on failure
  accessibility_notes: null           # free text, NON-medical (e.g., "prefers slower speech", "remove aids at night")
  last_reviewed_at: null              # ISO8601; OS/firmware updates invalidate verification — ADDED
```

Notes:
- `bidirectional_microphone_supported` is a *claim*. Only `verified_by_test.microphone` unlocks `preferred_input: hearing_aid`. This keeps "requested / claimed / verified" distinct.
- Re-verification triggers: an OS major version change, a new phone, a new aid, or new aid firmware.
- `room_audio_fallback` exists in the schema only so it is visible and auditable. It cannot be set to false.
- `fitting` is the only fitting detail stored, and it is needed for the binaural behaviour in §12.

---

## 9. Acceptance-test matrix (future — none run)

Common pass rule for every test: every reply is audible on some endpoint, every request created has a receipt, and every route decision and fallback is recorded with `requested/attempted/delivered/fallback`.

| ID | Setup | Steps | Pass criteria |
|---|---|---|---|
| **HA-01** | No hearing aids | Wake → request (light, front-desk message) | Mode A only; no personal route attempted; receipt present |
| **HA-02** | Non-Bluetooth aids (with/without T-coil) | Same as HA-01. Then lift the HAC handset with the aid in T-mode | Room conversation intelligible at normal seat distance; handset audible via T-coil; no Bluetooth dependency anywhere |
| **HA-03** | Bluetooth aids + iPhone (record exact models/OS) | Voice PE input, `preferred_output: hearing_aid` | Reply heard in the aids; the room speaker stays silent; route reported `bluetoothLE`; ack within T_ack |
| **HA-04** | Bluetooth aids + Android (ASHA case **and** LE Audio case, separately) | Same as HA-03 | As HA-03; route reported `TYPE_HEARING_AID` or `TYPE_BLE_HEADSET`; user selection behaviour on Android 14+ documented |
| **HA-05** | Combination claiming bidirectional | Phone surface, `preferred_input: hearing_aid`; speak with the phone in a pocket, more than 1 m from the mouth | Transcript is from the aid mic (prove it: cover/mute the phone mic, or check the reported input route); intelligibility ≥ the phone-mic baseline; recorded in `verified_by_test.microphone` |
| **HA-06** | Output-only device (ASHA, or MFi unidirectional) | Request the aid mic | System never claims the aid mic; uses the Voice PE or the phone mic; profile shows `bidirectional: no` |
| **HA-07** | HA-03/04 setup | Toggle Bluetooth off mid-reply; also power-cycle the aids mid-conversation | The current reply is completed or replayed on the room speaker; the next turn works; no lost request; fallback receipt |
| **HA-08** | Personal mode configured | Phone powered off / app killed / phone left in another apartment | Heartbeat loss → Mode A within one turn; nothing queued silently for the phone |
| **HA-09** | Bilateral set | Remove the battery from one aid during streaming | Observe and record OS behaviour (ASHA documents mixing to the remaining side [G1]; MFi/LE Audio/Classic to be measured); conversation continues; no false "delivered to both" |
| **HA-10** | Aria-initiated call (a) to the resident's mobile number; (b) on the HAC handset | Aria places a family/front-desk call | (a) call audio follows the phone's native hearing-device call routing, and the mic source is recorded per platform; (b) intelligible via T-coil; the call has a receipt in both cases |
| **HA-11** | Personal-capable resident who chooses room | `preferred_output: room` | No audio sent to the phone at all |
| **HA-12** | `both_alerts_only` | Trigger an announcement, then a normal reply | The announcement plays on both (measure the perceived offset and resident comfort); the normal reply plays on the personal route only; Live Listen interaction checked (§3.5) |
| **HA-13** *(added)* | Aid program switch mid-stream (resident-initiated) | Change program with the aid button/app | Stream continues or recovers within one turn; CAOSCare never sends program changes |
| **HA-14** *(added)* | Range | Walk out of phone Bluetooth range during a reply while staying near the Voice PE | Treated as HA-07; Mode A continues |

---

## 10. Hardware implications

1. **No new apartment hardware is needed for hearing aids.** Do not add Bluetooth radios, transmitters or EliteDesks to apartments for this purpose.
2. **D5 analog handset:** add the requirement **"hearing-aid compatible, telecoil-coupled (HAC/T-rated), with volume boost"**. Wireline telephones in the US are covered by FCC HAC rules [L1]. This is the cheapest, most universal hearing-aid call path, and it already exists in the Pilot 1 plan. *(This document does not edit `PILOT1_ROOM1_HARDWARE_INVENTORY.md`. Proposed for the coordinator.)*
3. **Common areas (future):** a hearing loop or an Auracast transmitter for the dining room/activity room is a facility decision. CAOSCare needs no integration with it. If an Auracast transmitter is ever fed from CAOSCare announcements, treat it as a broadcast output with no delivery confirmation.
4. **TV audio for hearing-aid users:** the resident's existing manufacturer TV streamer (most families sell one) stays outside CAOSCare. It is a separate playback path the room AEC cannot reference. For a resident using a TV streamer, the TV speakers may be muted while the resident hears TV in the aids. That is *better* for the Voice PE. Record it as a room configuration fact.
5. **Phone dock evaluation** (`CAOSCARE_PRODUCT_BASELINE.md`, managed Android phone + dock): a facility-managed Android phone **must not** be paired to resident hearing aids, for the reasons in §6.1. The resident's own phone is the bridge.

## 11. Software implications (proposed, not built)

1. **A phone-side Aria audio surface is required for Mode B.** Today, room replies render on the Voice PE through Home Assistant. Routing a reply to the phone needs a CAOSCare client on the resident's phone that holds an authenticated, room-scoped session and plays audio.
   - **Background audio is the hard part.** A web page in a backgrounded tab, or a locked phone, may not play audio. iOS especially restricts this. A native app with a background-audio entitlement may be required. **Unknown; spike needed.**
2. **Personal playback adapter.** Add "personal playback" as a logical output beside the roles in `ROOM_AUDIO_ARCHITECTURE.md`, following the `backend/device_adapters.py` pattern: a logical contract plus a transport. One output decision function (§7) is the single source of truth. Do not scatter checks across the voice code.
3. **Route reporting.** The phone client reports the current OS route (iOS `AVAudioSession.currentRoute` port types; Android `getCommunicationDevice()`/`AudioDeviceInfo` type). It reports what it observes, not what it was asked to do.
4. **Commit-then-render.** The request/receipt is written before audio rendering, so a rendering failure cannot lose the request (Mode E invariant).
5. **Do not set `deviceId`/`setSinkId` to force hearing aids from the web.** Follow the OS route. The resident and the audiologist control it.
6. **Never write hearing-aid presets/volume** (HAP HARC role [B1]). Out of scope, with fitting liability.

## 12. Unknowns requiring physical testing

1. Can an iOS third-party app (AVAudioSession `.playAndRecord`, `.allowBluetooth`/`.allowBluetoothHFP` options) get the microphone of a **bidirectional MFi** aid? Does selecting it as output force it as input [A6]?
2. Does Chrome/Android WebRTC `getUserMedia` use the LE Audio aid microphone automatically once the communication device is set, or only in a native app?
3. Real end-to-end latency and perceived doubling for Mode D, per platform (MFi, ASHA, LE Audio, Classic).
4. Single-aid loss behaviour on MFi, LE Audio and Classic (ASHA is documented [G1]).
5. Whether a program switch interrupts or re-routes the stream, per family.
6. Phone background-audio reliability (locked screen, low-power mode, Doze).
7. Whether the Voice PE microphone picks up enough of the resident's speech when the resident wears aids in "streaming" mode. Aids may lower their own mics while streaming, which matters to the *resident's* hearing of the room, not to capture. Also measure resident comprehension when the reply goes only to the aids and others in the room hear nothing.
8. Bluetooth range in the actual building (walls, elevator, corridors).
9. Current iOS Auracast status (no Apple primary source found).
10. How each test aid enumerates on Android (`TYPE_HEARING_AID` vs `TYPE_BLE_HEADSET`).

## 13. What NOT to promise yet

- "Works with your hearing aids", without naming the exact verified aid + phone + OS combination.
- "Talk to Aria through your hearing aids" (the aid microphone). Unproven on iOS for apps, impossible on ASHA, and limited to LE Audio/Classic combinations on Android.
- Any brand-level compatibility claim.
- Auracast private Aria audio, or Auracast on iPhone.
- Dual room + hearing-aid audio for conversation.
- Delivery confirmation "in the ear". CAOSCare can confirm, at most, that the phone played audio on a reported route.
- That CAOSCare can adjust hearing-aid programs or volume. It must not.
- Background/locked-phone delivery, until the §11.1 spike passes.

## 14. Sources (all accessed 2026-10-04)

**Apple (primary)**
- [A1] Use Live Listen with Made for iPhone hearing devices — https://support.apple.com/en-us/111777
- [A2] List of Made for iPhone hearing devices (system requirements; bidirectional brand list) — https://support.apple.com/en-us/106341
- [A3] iPhone User Guide, Hearing devices (iOS 15): audio routing / Lock Screen controls — https://support.apple.com/en-kg/guide/iphone/hearing-devices-iph470b1833/15.0
- [A4] iPhone User Guide, Stream audio to hearing devices / Call Audio Routing — https://support.apple.com/guide/iphone/stream-audio-to-hearing-devices-iph3d6f3f87c/12.0/ios
- [A5] AVAudioSession.Port: `bluetoothLE` ("An output to a Bluetooth Low Energy (LE) device"), `bluetoothHFP` ("An I/O connection…"), `bluetoothA2DP` — https://developer.apple.com/documentation/avfaudio/avaudiosession/port (abstracts read via developer.apple.com/tutorials/data/documentation/avfaudio/avaudiosession/port/{bluetoothle,bluetoothhfp,bluetootha2dp}.json)
- [A6] *(Apple Developer Forums; user post, no Apple reply — secondary)* Using separate BluetoothHFP devices for input and output, June 2026 — https://developer.apple.com/forums/thread/829524
- Use Made for iPhone hearing devices (pairing/general) — https://support.apple.com/en-us/108780

**Google / Android (primary)**
- [G1] Hearing aid audio support using Bluetooth LE (ASHA) — https://source.android.com/docs/core/connect/bluetooth/asha
- [G2] Hearing aid compatibility for Pixel phones — https://support.google.com/pixelphone/answer/9393002?hl=en
- [G3] Bluetooth Low Energy Audio overview — https://developer.android.com/develop/connectivity/bluetooth/ble-audio/overview
- [G4] Audio routing API updates in Android 14 for VoIP apps — https://developer.android.com/develop/connectivity/telecom/voip-app/api-updates
- [G5] AudioDeviceInfo reference (`TYPE_HEARING_AID`, `TYPE_BLE_HEADSET`, `TYPE_BLE_BROADCAST`) — https://developer.android.com/reference/android/media/AudioDeviceInfo

**Bluetooth SIG (primary)**
- [B1] Hearing Access Profile v1.0 (adopted 2022-06-07) — https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/12014-HAP-html5/out/en/index-en.html
- [B2] Support for Hearing Assistance — LE Audio — https://www.bluetooth.com/learn-about-bluetooth/feature-enhancements/le-audio/hearing/
- [B3] Answers to commonly asked questions about Auracast broadcast audio — https://www.bluetooth.com/blog/answers-to-commonly-asked-questions-about-auracast-broadcast-audio/
- An overview of Auracast broadcast audio (technical overview PDF) — https://www.bluetooth.com/wp-content/uploads/2024/05/2505_Paper_An-Overview-of-Auracast.pdf (listed; not quoted)

**Manufacturers (primary for their own products)**
- [M1] Phonak: Why do I see three Phonak hearing aids in my Bluetooth list — https://www.phonak.com/en-us/support/knowledge-base/articles/three-hearing-aids-in-the-bluetooth-phone-list ; Audéo Sphere features — https://www.phonak.com/en-us/hearing-devices/hearing-aids/audeo-sphere/features ; Audéo I-Sphere user guide (HFP/A2DP, pairing limits) — https://www.phonak.com/content/dam/celum/phonak/master-assets/en/documents/hearing-instruments/infinio/audeo-sphere/ph-user-guide-audeo-i-sphere-92x125-029-1356-02-en.pdf.coredownload.pdf
- [M2] Oticon: Intent product/campaign — https://www.oticon.com/campaigns-b2c/intent ; professional connectivity — https://www.oticon.com/professionals/hearing-solutions/connectivity ; Android pairing — https://www.oticon.com/support/pairing/android/how-to-pair-hearing-aids-with-android-devices ; Auracast sharing — https://www.oticon.com/support/life-with-a-hearing-aid/connecting-to-other-devices/how-to-share-audio-using-auracast
- [M3] ReSound: Compatibility — https://www.resound.com/en-us/help/compatibility ; Auracast hearing aids — https://www.resound.com/en-us/hearing-aids/auracast-hearing-aids
- [M4] Starkey: Device compatibility — https://www.starkey.com/compatibility ; Omega AI connectivity press release (2026-01) — https://www.starkey.com/press/press-releases/2026/01/starkey-expands-omega-ai-connectivity
- [M5] Signia: Connectivity & pairing support — https://www.signia.net/en-us/support/pairing/ ; Pure Charge&Go BCT IX — https://www.signia.net/en-us/hearing-aids/integrated-xperience/pure-charge-go-ix/bluetooth-connectivity-transformed/
- [M6] Widex: Pairing support — https://www.widex.com/en/support/pairing/ ; Compatibility — https://www.widex.com/en-us/support/compatibility/

**Regulatory / accessibility**
- [L1] FCC: Hearing Aid Compatibility for wireline and wireless telephones — https://www.fcc.gov/consumers/guides/hearing-aid-compatibility-wireline-and-wireless-telephones ; HAC mobile handsets — https://www.fcc.gov/hearing-aid-compatibility-wireless-telephones
- [L2] U.S. Access Board: Large Area Assistive Listening Systems review — https://www.access-board.gov/files/research/assistive-listening-systems.pdf ; HLAA "Get in the Hearing Loop" guide — https://www.hearingloss.org/wp-content/uploads/documents/advocacy-resources/githl/githl-guide-to-understanding-hearing-loops-print.pdf

**Secondary (used only where primary documentation was silent)**
- [S2] Listen Technologies, "Auracast on iPhone" (2025-09-03) — https://www.listentech.com/auracast-on-iphone/

**Research method and limits.** Pages were retrieved through web search plus page fetches, and quotes were taken from the fetched text. Some Apple and Phonak pages render through JavaScript and could only be read partially. Where a fetch returned no relevant text, this document makes no claim from that page. Manufacturer compatibility pages change often, so re-check them before any resident-facing statement.
