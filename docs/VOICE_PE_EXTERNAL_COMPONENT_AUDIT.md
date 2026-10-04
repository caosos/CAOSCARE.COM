# Voice PE external component audit — Phase 1 (2026-10-04)

Scope: read-only study of existing Voice PE systems as a parts warehouse for
CAOSCare.

- Nothing was copied into CAOSCare, nothing external was executed, and
  nothing was installed, built or flashed.
- Sources were read through the GitHub API at the pinned commits listed in
  §14.
- Inspection window: 2026-10-04 08:48–09:15 CDT, on `caoscare1-hp-elitedesk`
  (branch `spike/voice-bridge`, HEAD `27dd6e8` at start).

Evidence labels:

- **[src]**: confirmed in source.
- **[doc]**: README or documentation claim only, not confirmed in source.
- **[inf]**: my inference.

## 1. Executive conclusion

All five non-official systems replace the stock firmware's
Home Assistant (HA) Assist path with a custom **`va_client`** ESPHome
component. It streams raw PCM over a WebSocket to a backend that runs an
OpenAI Realtime speech-to-speech session and controls HA through the HA MCP
Server. They are well engineered for a single household.

None of them is suitable to adopt as-is for a care facility:

1. **Transport security is absent or weak.** Of the custom-firmware
   backends:
   - Two accept **unauthenticated, plaintext `ws://`** device connections:
     xandervanerven and TristanBrotherton.
   - maxmaxme adds a per-device bearer token, but sends it, and the audio,
     over **plaintext `ws://`**.
   - havpe-server requires **removing ESPHome API encryption** from the
     device.
2. **Identity is the household, not the resident.** Each runs one assistant
   with its own memory, tools and policy. Adopting any of them as the brain
   would create a second assistant and a second request/memory universe,
   which conflicts with CAOSCare's canonical models.
3. **Licences.**
   - Every custom firmware is the ESPHome licence (C++ under GPLv3).
   - maxmaxme/voice-assistant and havpe-server are **AGPL-3.0**.
   - The two Python backends are MIT.

**Recommendation.**

- Keep CAOSCare's current architecture: stock, encrypted Voice PE firmware →
  HA Assist satellite → CAOSCare conversation agent over the voice bridge.
- Take *ideas* (REFERENCE) from these projects for the gaps CAOSCare actually
  has:
  - wake arbitration across co-located devices;
  - room-targeted announcements;
  - a server-owned follow-up window;
  - session refresh and reconnect recovery;
  - turn admission against accidental wakes.
- Build them inside CAOSCare's existing interfaces.
- The only things to ADOPT are official HA/ESPHome contracts:
  - the stock firmware;
  - the Assist satellite `announce` / `start_conversation` services;
  - `ConversationInput.device_id` / `satellite_id`;
  - `ConversationResult.continue_conversation`;
  - the area registry.
- A realtime speech-to-speech path (custom `va_client` firmware) is a separate,
  later decision for Michael (§13). It is not required for Pilot 1.

## 2. Repository provenance

| # | Repository | Owner | Inspected commit (commit date) | Licence (file) | Commercial use | Obligations | Activity |
|---|---|---|---|---|---|---|---|
| 1 | https://github.com/esphome/home-assistant-voice-pe | esphome (Nabu Casa) | `d4e6fa43d6a1a7d342b7d4d403567e06516719de` (2026-09-17), branch `dev` | ESPHome licence: GPLv3 for C/C++, MIT for Python and YAML (`LICENSE`). Hardware CERN-OHL-P v2 (`hardware/LICENSE.txt`). Sounds CC BY 4.0 (`sounds/LICENSE.md`). | Yes (use and ship) | Source of modified GPLv3 firmware must be offered with distributed devices; sound attribution | Active (pushed 2026-09-29, 765 stars) |
| 2 | https://github.com/xandervanerven/home-assistant-voice-pe | xandervanerven | `763a87a85fe2f86b6aa819e6b4cbc6bd6943f796` (2026-06-15), `main` | ESPHome licence (`LICENSE`) | Yes, GPLv3 terms for `va_client` C++ | GPLv3 source disclosure if shipped | Low (last push 2026-06-15, 9 stars). Fork of maxmaxme/home-assistant-voice-pe [doc: README]. |
| 3 | https://github.com/xandervanerven/ha-openai-realtime | xandervanerven | `3edc58679a7f59dce1d31e0a7e5784d04c179f79` (2026-06-15), `main` | MIT (`LICENSE`) | Yes | Keep copyright/licence notice | Low (2026-06-15). GitHub fork of fjfricke/ha-openai-realtime. |
| 4 | https://github.com/maxmaxme/voice-assistant | maxmaxme | `3f3461052cd5b46c5015c98ed88294ca44cd7823` (2026-10-04), `main` | **AGPL-3.0** (`LICENSE`) | Only with AGPL compliance: network users must be offered full source of modified versions | Strong copyleft over the network | Very active (pushed today); 2 stars |
| 5 | https://github.com/maxmaxme/home-assistant-voice-pe (linked from #4 README) | maxmaxme | `5f894ae584cc166c0d6bae287cd114b186451deb` (2026-08-10), `dev` | ESPHome licence (`LICENSE`) | Yes, GPLv3 for C++ | GPLv3 source disclosure | Moderate (2026-08-10); has host tests |
| 6 | https://github.com/TristanBrotherton/voicepe-realtime | TristanBrotherton | `4ee92fe33b78de76274fd6050446bd1e9ac0a7ff` (2026-10-01), `main` | MIT (`LICENSE`) | Yes | Notice. Derived from fjfricke (MIT) [doc: README Credits]. | Active (2026-10-01, 89 stars) |
| 7 | https://github.com/TristanBrotherton/voicepe-realtime-firmware (linked from #6 README) | TristanBrotherton | `e56ee1259c09de6557cea571327b82bbf0928109` (2026-09-30), `main` | ESPHome licence (`LICENSE`). Ships `models/hey_leonard.tflite`, whose licence was not stated in files inspected. | C++ yes under GPLv3; wake model unclear | GPLv3 disclosure; model provenance unknown | Active |
| 8 | https://github.com/skorokithakis/havpe-server | skorokithakis | `14555cca6eae9dec2f434fe729f05eb9bfd3a748` (2026-04-07), `master` | **AGPL-3.0** (`LICENSE`) | Only with AGPL compliance | Network copyleft | Low (2026-04-07, 1 star) |
| 9 | https://github.com/home-assistant/core (API contracts only) | home-assistant | `275e8b6a02c5f5786a7f8a1bbafa68e3100a27eb` (2026-10-04), `dev` | Apache-2.0 | n/a: CAOSCare only *calls* these APIs | none for API use | Active |

## 3. Architecture of each system

**#1 Official firmware** [src `home-assistant-voice.yaml`]

- ESPHome on ESP32-S3 with an XMOS front end.
- `api:` has `encryption:` with a key set by HA (Noise-encrypted native API),
  lines 108–114.
- `micro_wake_word` runs on the device with okay_nabu, hey_jarvis,
  hey_mycroft and `stop` (lines 1722–1737; per-model cutoffs at 1799–1812).
- `voice_assistant:` streams audio to the HA Assist pipeline (line 1815). It
  has callbacks for listening, STT VAD, intent progress, TTS, end, and timer
  started/updated/finished/cancelled.
- Hardware and software mute switches (lines 191–217, 519–539).
- Factory image: `ota: http_request`, `update:` from
  `firmware.esphome.io`, improv serial/BLE provisioning, `dashboard_import`
  (`home-assistant-voice.factory.yaml`).

**#2 + #3 xandervanerven** [src]

- Firmware: `va_client` (`esphome/components/va_client/va_client.{h,cpp}`)
  opens `esp_websocket_client` with only `cfg.uri` set (cpp 284–288). There
  are no headers, no TLS settings and no device id.
- Default `va_url: "ws://homeassistant.local:8080/"`
  (`home-assistant-voice.realtime.yaml:61`).
- JSON control frames: `start`, `wake`, `interrupt`, `flush`; server sends
  `hello`, `error` and `request_follow_up` (cpp 369, 424–481, 1014–1195).
  Binary PCM both ways.
- Phase state machine IDLE / LISTENING / THINKING / REPLYING (h 136). "stop"
  wake word armed only while replying (yaml 384–413, 1685–1715).
- ESPHome API encryption is kept (`secrets.yaml.example`, INSTALL §2.3).
- Backend: an HA add-on with `host_network: true`, port 8080
  (`config.yaml` 12, 102). It runs a Pipecat `WebsocketServerTransport` on
  `0.0.0.0` with no authentication (`app/main.py` 233–234,
  `app/websocket_handler.py` 381–412).
- A **single shared OpenAI service** per add-on (`main.py` 492–514).
- HA is controlled through the MCP Server with a long-lived token
  (`app/mcp_service.py`).

**#4 + #5 maxmaxme** [src]

- Backend (Node/TypeScript, AGPL): WS server on `/voice`. The handshake
  requires `Authorization: Bearer <token>`, hash-matched against registered
  voice identities; otherwise close 4401 (`src/realtime/wsServer.ts` 69–77,
  `src/realtime/auth.ts`).
- Versioned protocol (`src/realtime/protocol.ts`, `PROTO_VERSION = 1`). The
  server owns the `follow_up` window.
- Wake arbitration de-duplicates co-located wakes
  (`src/realtime/wakeArbiter.ts`).
- SQLite memory with household/personal scopes, cron scheduler, goal runner
  and MCP client (`src/memory/*`, `src/scheduling/*`, `src/mcp/*`). Tests
  under `tests/`.
- Firmware: sends the bearer header (`va_client.cpp` 454–458) and has a
  30-second ping-pong dead-link timeout. URL is `ws://va.local:3001/voice`
  (yaml 34), so the **token and audio travel in cleartext**.
- Host unit tests exist for `va_core` (`tests/host/`).

**#6 + #7 TristanBrotherton** [src]

- Backend: fork of the fjfricke lineage, extended with:
  - per-device connections (`app/device_registry.py`, `app/multi_client_transport.py`);
  - device id taken from `?device_id=` with an IP fallback, sanitised but
    **self-asserted** (`device_registry.py` 18–60);
  - backend timers that ring on the originating device (`app/timers.py`);
  - announcements over a bearer-token HTTP endpoint (`app/announce_http.py` 9–50);
  - speaker recognition with voiceprints and tool gating that "fails closed"
    (`app/speaker_context.py`, `voiceprint.py`, `enrollment.py`);
  - voice memory (`app/voice_memory.py`);
  - OpenClaw task delegation (`app/openclaw_tool.py`);
  - turn-admission rules (`app/turn_admission.py`);
  - 10 test files under `tests/`.
- Device WebSocket: no authentication code found in `websocket_handler.py`.
- Firmware is `va_client`-based with an enrollment mode and ships a custom
  `hey_leonard` wake model.

**#8 havpe-server** [src + doc]

- Go server acting as an ESPHome native-API *client*
  (`proto/api.proto`, `main.go` message types 89–106).
- The device's `api: encryption` must be removed (plaintext, no
  authentication) [doc: README "Preparing the Voice PE firmware"].
- ElevenLabs STT/TTS, then a webhook POST.
- Regex "shortcuts" call URLs (a Basic-auth CRUD API).
- Records activations to numbered WAV files (`main.go` comment at line 199).

**#9 HA core contracts** [src]

- `conversation.ConversationInput` carries `device_id` and `satellite_id`;
  `ConversationResult.continue_conversation` exists
  (`homeassistant/components/conversation/models.py` 23–87).
- Assist satellite services: `announce`, `start_conversation`, `ask_question`
  (`assist_satellite/services.yaml`; `entity.py` 198–249).
- The ESPHome satellite passes `continue_conversation` to the device
  (`esphome/assist_satellite.py` 384).
- The MCP Server exposes LLM APIs at `/api/mcp`. Non-Assist APIs and the
  "require admin" option are restricted to admins (`mcp_server/http.py`
  103–115, 364–369).

## 4. Component comparison matrix

| Component | #1 official | #2/#3 xander | #4/#5 maxmaxme | #6/#7 Tristan | #8 havpe | CAOSCare today |
|---|---|---|---|---|---|---|
| Bidirectional audio | HA pipeline (encrypted API) | plaintext WS, PCM | plaintext WS, PCM | plaintext WS, PCM | plaintext native API | via HA pipeline (staged STT→text→TTS) |
| Device authentication | Noise PSK [src] | none [src] | bearer token over ws:// [src] | none on device WS [src] | none (encryption removed) | HA ↔ device Noise; HA → CAOSCare bridge token (`CAOSCARE_VOICE_BRIDGE_TOKEN`) |
| Room/device identity | HA device registry + area | none | token → principal | self-asserted `device_id` | mDNS name | `Kiosk.voice_device_ids` → room → resident [src `voice_bridge_session.py`] |
| Multi-device routing | HA | single session | per-device bridge + wake arbiter | device registry, most-recent default | single device | per-device session; no wake arbitration |
| Wake word | on-device mWW | on-device mWW | on-device | custom model | n/a | stock; "Hey Aria" in the firmware lane |
| LED/phase state machine | stock | server-driven phases | server-driven | server-driven | n/a | stock (HA pipeline events) |
| Stop / barge-in | stop word (pipeline) | stop word + button → `interrupt` | `start` = barge-in | yes | n/a | stock stop; no realtime barge-in (staged path) |
| Continued conversation | `continue_conversation` | server `request_follow_up` | server `follow_up` | yes | no | returns `continue_conversation` [src] |
| Deterministic ending | pipeline end | n/a | n/a | n/a | n/a | closing phrases, no model call, receipt [src] |
| Timers/reminders | HA timers (device callbacks) | none [doc] | cron scheduler | backend timers, room ring | no | none on bridge |
| Announcements to a room | `assist_satellite.announce` | no | no | HTTP announce (bearer) | no | none on bridge |
| Tool execution | HA intents | HA MCP (LLAT) | HA MCP | HA MCP + OpenClaw | webhook | canonical CAOSCare services; device commands via `execute_room_command` |
| Memory scopes | n/a | none | household/personal | voice memory, speaker-gated | none | resident memory (two bins), layers B/C/E |
| Speaker recognition | no | no | no | voiceprints | no | none (not an identity proof) |
| Receipts/provenance | no | no | no | no | no | per-turn chained receipts, origin authority [src] |
| Admission/capacity | n/a | n/a | n/a | turn admission (prompt rule) | n/a | priority admission, emergency fast path, load-tested |
| OTA/recovery | http_request update, improv, factory image | ESPHome dashboard | ESPHome | ESPHome | n/a | stock (official) |
| Reconnect/session refresh | HA | proactive refresh before 60-min cap | ping-pong + backoff | refresh + recovery tests | n/a | per-turn HTTP (no long-lived session) |
| Tests | n/a | none found | yes (TS + host C++) | yes (10 files) | Go tests | yes (bridge flow/units/load) |

## 5. Licence findings

- **ESPHome firmware (#1, #2, #5, #7):**
  - C/C++ is GPLv3; Python and YAML are MIT.
  - Shipping a modified firmware on devices CAOSCare installs obliges
    offering the corresponding source, including any `va_client` C++ (GPLv3).
  - Stock firmware used unmodified is the simplest position.
- **Sounds (#1):** CC BY 4.0, which requires attribution to Clayton Charles
  Tapp if redistributed.
- **AGPL-3.0 (#4 maxmaxme/voice-assistant, #8 havpe-server):** incorporating
  or modifying either in CAOSCare's network service would require offering
  CAOSCare's corresponding source to its network users. **Do not incorporate
  code.** Reading for ideas only.
- **MIT (#3, #6):** permissive.
  - Code could be adapted with notice.
  - Both are Pipecat-based. Pipecat's licence (BSD-2 at time of writing,
    [inf], not verified in this audit) would also apply.
- **Wake model (#7):** `hey_leonard.tflite` has no licence statement in the
  files inspected. **Unknown; do not use.**
- **HA core:** Apache-2.0; calling its APIs creates no obligation.

## 6. Security and privacy findings

1. **REJECT plaintext device control.** These projects transmit room audio
   and drive home control in cleartext:
   - #2/#3 and #6: unauthenticated `ws://`, with the backend bound to
     `0.0.0.0` on the host network. Anyone on the LAN can stream audio in
     and trigger HA actions through the MCP token.
   - #5: bearer token over plaintext `ws://`.
   - #8: requires removing ESPHome API encryption.

   In a care facility this exposes resident speech and allows spoofed
   commands.
2. **Self-asserted device identity (#6):** `?device_id=` is chosen by the
   client and the IP fallback is unstable. CAOSCare must derive the room from
   a credential-bound device, as it does now with the HA device id under an
   authenticated bridge call.
3. **Speaker recognition (#6)** is a convenience signal. **Not identity or
   authorisation proof.** CAOSCare must never gate care actions or reveal
   resident data on a voiceprint.
4. **Long-lived HA token with broad MCP scope (#3, #6):**
   - The model can drive any entity exposed to Assist.
   - CAOSCare already routes device control through its own scoped room
     command (`devices.execute_room_command`) with room isolation and
     receipts.
   - MCP would be a second, unscoped control path.
5. **Audio recordings:**
   - #8 writes activation WAVs.
   - #3/#6 have `audio_recorder.py` and `audio_recording_service.py`.
   - Any recording in CAOSCare needs a consent and retention policy; none is
     defined.
6. **Cloud boundary:** all realtime variants stream post-wake audio to OpenAI.
   The CAOSCare bridge sends text only. Moving to realtime changes what leaves
   the building.

## 7. Overlap with current CAOSCare

CAOSCare already has [src, `spike/voice-bridge`]:

- authenticated bridge;
- device → room → resident mapping with admin receipts;
- per-session binding and cross-room refusal;
- deterministic closing phrases;
- chained per-turn receipts;
- priority admission with reserved staff-help slots;
- emergency fast path (no model);
- arrival-claim guard;
- server-side tool executor over the canonical services;
- per-resident memory and layers B/C/E;
- capacity monitoring;
- a load harness.

None of the external systems has receipts, provenance, resident scoping,
admission or emergency priority.

Adopting any external brain (#3/#4/#6/#8) would duplicate all of this. That
is a parallel pathway, rejected under the one-source-of-truth invariant.

## 8. Adopt / Adapt / Reference / Reject

Answers to the ten required questions, per mechanism.

| Mechanism | Decision | CAOSCare requirement | Already in CAOSCare? | Parallel path if adopted directly? | Canonical home | Actor/receipt data | Boundary | Failure state to expose | Proving tests | Physical acceptance | Complexity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Stock encrypted Voice PE firmware (#1) | **ADOPT** | room gateway | yes (chosen) | no | device layer (HA) | device id in receipts | Noise-encrypted API | device offline / unavailable | n/a (vendor) | real-room mic/speaker | none |
| `ConversationInput.device_id`/`satellite_id` → room (#9) | **ADOPT** | room/device identity | yes | no | `voice_bridge_session.resolve_identity` | device id → kiosk → resident | bridge token | unknown device → refusal receipt | existing flow tests | map each real device | done |
| `continue_conversation` (#9) | **ADOPT** | follow-up without re-wake | yes | no | bridge response | session state | — | dropped follow-up | flow test | real Voice PE reopens mic | done |
| `assist_satellite.announce` / `start_conversation` (#9) | **ADOPT** (HA service) | room-aware result announcements, staff/system messages to a room | no | no, if called by a CAOSCare service | new announce service behind a canonical `announce_to_room(room, text, actor, workflow)` | actor, room, origin object, receipt `room_announced` / `room_announce_failed` | staff/system only; never another room | satellite busy, unavailable, failed | unit + HA stub; refusal for wrong room | announcement plays in the right room only | M |
| Area registry for room context (#9) | **REFERENCE** (cross-check) | detect mapping drift | partly (CAOSCare mapping is canonical) | yes if HA areas became the source | mapping admin check | mismatch receipt | admin | "device area ≠ CAOSCare room" warning | unit | — | S |
| Wake arbitration across co-located devices (#4 `wakeArbiter.ts`) | **REFERENCE** | prevent double answers if two endpoints hear one room | no | no | bridge `claim_turn` (per-room window) | room, both devices, winner | — | duplicate suppressed (receipt) | unit + load scenario | two devices, one room | S |
| Server-owned follow-up window (#4 `follow_up`, #2 `request_follow_up`) | **REFERENCE** | consistent follow-up length; ask-a-question flows | partial (boolean only) | no | bridge response policy | session | — | window expired | flow test | real device timing | S (needs HA support check) |
| Turn admission against accidental wakes (#6 `turn_admission.py`) | **REFERENCE** | false-wake resilience | no | no | resident prompt rule + bridge (no reply, no tool) | `voice_turn_ignored` receipt | — | ignored turn | prompt-contract test + transcript fixtures | TV/background audio in room | S |
| Backend timers ringing the originating device (#6 `timers.py`) | **REFERENCE** | reminders/timers for residents | no | yes, if a second timer store | CAOSCare reminders on the schedule/StaffTask spine + `announce_to_room` | resident, room, actor, receipts on set/fire/ack | resident's own room | fire failed / undelivered | unit + scheduler test | timer heard in room | M |
| Long-running task delegation + report back (#6 OpenClaw) | **REJECT** as is / REFERENCE pattern | "we'll let you know" outcomes | partly: request lifecycle | yes (external agent) | existing request lifecycle + announce on state change | full chain | staff-mediated | — | — | — | — |
| Realtime S2S transport `va_client` + backend (#2/#3/#5/#6/#7) | **REFERENCE** (Phase 2 decision) | low-latency natural conversation, barge-in | no (staged path) | yes, unless it terminates in CAOSCare | a future CAOSCare-owned realtime endpoint with TLS (`wss`), per-device credential, CAOSCare tools and receipts | same as bridge | must be wss + per-device auth | stream drop / reconnect | protocol + reconnect + receipt tests | full room acceptance | L |
| Session refresh before the 60-min cap, reconnect watchdogs (#3/#6) | **REFERENCE** | only if realtime adopted | n/a | — | realtime endpoint | — | — | — | `test_connection_recovery.py` pattern | — | in L |
| Stop word arming only while replying (#2 yaml) | **REFERENCE** | fewer false stops | stock behaviour | no | firmware lane | — | — | — | — | real room | firmware lane |
| HA MCP Server for device control (#3/#4/#6) | **REJECT** for resident actions | — | CAOSCare has scoped room commands | yes | — | — | broad LLAT scope | — | — | — | — |
| Speaker recognition / voiceprints (#6) | **REJECT** as identity; possible future personalisation only after a privacy decision | — | — | — | — | — | biometric data | — | — | — | — |
| Household memory scopes (#4) | **REJECT** | — | resident memory exists | yes | — | — | — | — | — | — | — |
| Plaintext native-API server (#8) | **REJECT** | — | — | yes | — | — | removes encryption | — | — | — | — |
| `hey_leonard` model (#7) | **REJECT** | — | — | — | — | — | unknown licence | — | — | — | — |
| Host-side unit tests of the device state machine (#5 `tests/host`) | **REFERENCE** | firmware-lane testing practice | — | — | firmware lane | — | — | — | — | — | — |

## 9. Recommended minimal CAOSCare architecture

```
Voice PE (stock firmware, Noise-encrypted API, on-device wake word)
  → Home Assistant Assist satellite (STT / TTS by HA pipeline)
  → caoscare_conversation agent  (device_id, satellite_id, conversation_id)
  → CAOSCare /api/voice-bridge/turn  (bridge token, device→room→resident)
  → canonical services (requests, devices, menu, schedule, transport, help)
  → receipts + provenance
CAOSCare → assist_satellite.announce (room-targeted, receipted)   [new, small]
```

No second assistant, no second memory, and no plaintext transport.

Realtime speech-to-speech stays a documented option (§13). If chosen, it must:

- terminate in a CAOSCare-owned endpoint;
- use `wss`, per-device credentials and the same tools and receipts;
- never run as an external add-on brain.

## 10. Components explicitly rejected

- Unauthenticated or plaintext device transports (#2/#3/#6 device
  WebSocket, #5 over `ws://`, #8 encryption removal).
- External assistant backends as the brain (#3, #4, #6, #8): parallel
  assistant, memory and tool universe.
- AGPL code incorporation (#4, #8).
- HA MCP with long-lived tokens for resident actions.
- Speaker recognition as identity or authorisation.
- Household memory scopes.
- OpenClaw delegation.
- `hey_leonard` model (unknown licence).
- Audio recording without a consent and retention policy.

## 11. Ordered implementation slices (proposals; none implemented)

1. **Room announcements.**
   - A canonical `announce_to_room` service calling HA
     `assist_satellite.announce` for the room's mapped satellite.
   - Receipts for announced / failed / refused.
   - Staff/system actors only.
2. **Wake/turn de-duplication per room.**
   - Extend the bridge's `claim_turn` with a short per-room window, so two
     endpoints in one room do not create two turns.
3. **Turn admission.**
   - An accidental-wake rule in the resident prompt, checked by the prompt
     contract.
   - The bridge records `voice_turn_ignored` when the model returns no
     speech.
4. **Reminders/timers on CAOSCare's schedule spine.**
   - Delivered through slice 1. Depends on a decision on who may set them.
5. **Area-registry drift check** in the device-mapping admin. Warn only.
6. **(Decision-gated) realtime endpoint design.**
   - Threat model (`wss`, device credential, rotation).
   - Protocol (reference #4 `protocol.ts` shape).
   - Firmware-lane coordination.
   - Cost and capacity.

## 12. Tests and physical acceptance required

For each slice:

- **Unit tests:** the service against an HA stub, wrong room refused,
  satellite unavailable, receipts chained.
- **Flow tests** through `/api/voice-bridge/turn`.
- **Load scenario** for the announcement fan-out.

Physical, per room:

- an announcement plays only in the target room;
- two devices in one room produce one answer;
- TV/background audio does not open a conversation;
- a reminder is heard and acknowledged;
- the device recovers after HA or CAOSCare restarts.

Still open from the bridge lane: the first real Voice PE acceptance itself
(`docs/VOICE_PE_BRIDGE_INSTALL.md` §9).

## 13. Open questions for Michael

1. Realtime speech-to-speech (custom `va_client` firmware) vs. the current
   staged HA pipeline for Pilot 1:
   - Realtime adds barge-in and natural timing.
   - It also brings a custom GPLv3 firmware to maintain, a security build
     (`wss`, per-device credentials), cloud audio streaming and higher cost.
2. Who may make CAOSCare speak in a room (announcements): staff roles,
   system workflows, family?
3. Are resident reminders/timers in scope, and who may set them (resident by
   voice, staff)?
4. Are any audio recordings acceptable (debugging, false-wake tuning)? If so,
   what consent and retention apply?
5. Speaker recognition: rule it out entirely, or allow it later for
   personalisation only (never authorisation)?
6. If a custom firmware is ever shipped to communities: approve the GPLv3
   source-offer obligation.

## 14. Exact sources and commit SHAs

| Repository | Commit | Key files read |
|---|---|---|
| esphome/home-assistant-voice-pe | `d4e6fa43d6a1a7d342b7d4d403567e06516719de` | `LICENSE`, `README.md`, `sounds/LICENSE.md`, `hardware/README.md`, `home-assistant-voice.yaml` (api 108–114, wake 1722–1812, voice_assistant 1815+), `home-assistant-voice.factory.yaml` |
| xandervanerven/home-assistant-voice-pe | `763a87a85fe2f86b6aa819e6b4cbc6bd6943f796` | `LICENSE`, `README.md`, `INSTALL.md`, `esphome/components/va_client/va_client.{h,cpp}`, `home-assistant-voice.realtime.yaml` |
| xandervanerven/ha-openai-realtime | `3edc58679a7f59dce1d31e0a7e5784d04c179f79` | `LICENSE`, `README.md`, `openai_realtime_voice_agent/config.yaml`, `app/main.py`, `app/websocket_handler.py`, `app/mcp_service.py` |
| maxmaxme/voice-assistant | `3f3461052cd5b46c5015c98ed88294ca44cd7823` | `README.md`, `src/realtime/{auth,protocol,wsServer,wakeArbiter}.ts`, tree listing |
| maxmaxme/home-assistant-voice-pe | `5f894ae584cc166c0d6bae287cd114b186451deb` | `README.md`, `va_client.cpp` 445–470, `home-assistant-voice.va-direct.yaml` 34, 1566–1567, tree listing |
| TristanBrotherton/voicepe-realtime | `4ee92fe33b78de76274fd6050446bd1e9ac0a7ff` | `LICENSE`, `README.md`, `app/{device_registry,announce_http,turn_admission,speaker_context,timers,multi_client_transport,websocket_handler}.py`, tests listing |
| TristanBrotherton/voicepe-realtime-firmware | `e56ee1259c09de6557cea571327b82bbf0928109` | `LICENSE`, tree listing, `va_client.cpp` grep |
| skorokithakis/havpe-server | `14555cca6eae9dec2f434fe729f05eb9bfd3a748` | `LICENSE`, `README.md`, `main.go` grep |
| home-assistant/core | `275e8b6a02c5f5786a7f8a1bbafa68e3100a27eb` | `conversation/models.py`, `assist_satellite/entity.py`, `assist_satellite/services.yaml`, `esphome/assist_satellite.py`, `mcp_server/http.py`, `mcp_server/manifest.json` |
| CAOSCare (compared, unchanged) | `27dd6e871ccb1fccd1c73869ad9d206cc2869255` | `backend/routes/voice_bridge*.py`, `integrations/home_assistant/custom_components/caoscare_conversation/*`, `docs/VOICE_PE_BRIDGE_INSTALL.md` |

Not verified:

- runtime behaviour of any external project;
- Pipecat's licence;
- HA documentation pages beyond the source files listed.

Resources during the audit:

- Available RAM stayed at 8.3–9.1 GB.
- Swap was full (2.0 GB) before the audit started.
- No swap activity was observed (`vmstat` si/so = 0).
- The wake lab advanced from `callista_call_iss_tuh` to `kestra_kess_truh`.
