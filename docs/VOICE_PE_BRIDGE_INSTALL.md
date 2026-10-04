# Voice PE → CAOSCare voice bridge: installation and verification

Status (2026-10-03): the CAOSCare side and the Home Assistant agent's HTTP
client are tested with simulated Home Assistant requests. **Not yet done:**
installing the agent in Home Assistant, configuring speech-to-text and
text-to-speech, and testing with a physical Voice PE in a room. Wake word and
Voice PE firmware belong to the firmware lane and are not covered here.

## 1. What runs where

```
Voice PE (room) --Wi-Fi--> Home Assistant (central EliteDesk VM)
   wake word, mic, speaker      Assist pipeline: STT -> CAOSCare agent -> TTS
                                        |
                                        | POST /api/voice-bridge/turn
                                        v
                               CAOSCare backend (central EliteDesk)
                               device -> room -> resident, conversation,
                               tools, requests, receipts
```

Home Assistant sends only: the transcript, its conversation id, the Voice PE's
HA device id (and satellite entity id when available), and the language.
CAOSCare decides who the resident is from its own device mapping; it never
uses a room number the resident says.

## 2. Required files

CAOSCare backend (branch `spike/voice-bridge`):

| File | Purpose |
|---|---|
| `backend/routes/voice_bridge.py` | `POST /api/voice-bridge/turn` |
| `backend/routes/voice_bridge_session.py` | device→room→resident, sessions, closing phrases, retry detection |
| `backend/routes/voice_bridge_receipts.py` | one receipt per turn; refusal receipts |
| `backend/routes/voice_bridge_tools.py` | menu, schedule, staff request, request status/history, time, end call |
| `backend/routes/voice_bridge_devices.py` | admin mapping of Voice PE devices to rooms |
| `backend/routes/voice_bridge_config.py` | provider/model selection and validation |
| `backend/serve.py` | backend launcher with a validated bind address |

Home Assistant custom integration: copy the whole folder
`integrations/home_assistant/custom_components/caoscare_conversation/`
(`__init__.py`, `manifest.json`, `config_flow.py`, `conversation.py`,
`bridge_client.py`) to `/config/custom_components/caoscare_conversation/` in
Home Assistant (Samba or SSH add-on, or the File editor).

## 3. CAOSCare configuration (backend `.env`, never committed)

| Variable | Required | Meaning |
|---|---|---|
| `CAOSCARE_VOICE_BRIDGE_TOKEN` | yes | Shared secret Home Assistant sends as `Authorization: Bearer …`. Unset → the bridge answers 503. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `OPENAI_API_KEY` | yes | Already used by CAOSCare. |
| `CAOSCARE_VOICE_BRIDGE_PROVIDER` | no | Default `openai` (the only provider wired). |
| `CAOSCARE_VOICE_BRIDGE_MODEL` | no | Default `gpt-4o-mini`. Accepted: `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-4o` (`backend/routes/voice_bridge_config.py`). Any other value disables the bridge (turns answer 503 with the reason); it never silently falls back to another model. The selection is logged at backend startup (`voice bridge model: openai/<model>` or `voice bridge disabled: …`). Live-tested on the bridge: gpt-4o-mini and gpt-4.1; in the 2026-10-03 spike gpt-4.1 behaved better (the arrival guard and deterministic goodbyes now cover gpt-4o-mini's two observed faults). Choose before the pilot. |
| `CAOSCARE_VOICE_BRIDGE_BUDGET_S` | no | Time budget per turn, default 18 s (Home Assistant's agent gives up at 25 s). |
| `CAOSCARE_BIND_HOST` / `CAOSCARE_BIND_PORT` | no | Used by `backend/serve.py` (below). Default `127.0.0.1` / `8000`. |

**Network:** the Home Assistant VM reaches the host at `192.168.122.1`
(libvirt bridge `virbr0`). A backend bound to `127.0.0.1` is **not
reachable** from Home Assistant. Start the backend that serves the bridge
with the validated launcher:

```
cd backend && CAOSCARE_BIND_HOST=192.168.122.1 CAOSCARE_BIND_PORT=<port> .venv/bin/python serve.py
```

`serve.py` accepts only `127.0.0.1` (default), `::1` and `192.168.122.1`;
`0.0.0.0`, `::` and any other address are refused (the process exits with
the reason). `192.168.122.1` is reachable from the VMs on that bridge, not
from the building network. Not yet switched on at the EliteDesk.

Restart the backend after changing `.env`. On startup it creates the
`voice_bridge_sessions` indexes.

## 4. Map each Voice PE to its room

1. Find the Voice PE's Home Assistant device id: Settings → Devices &
   services → Devices → open the Voice PE. The address bar ends with
   `/config/devices/device/<device_id>`.
2. Find the room's endpoint (kiosk) id in CAOSCare: Admin → Kiosks, or
   `GET /api/kiosks`. The kiosk's room must have the resident assigned.
3. Map it (owner/admin login required):
   ```
   curl -X PUT http://<caoscare>/api/voice-bridge/devices/<device_id> \
        -H "Authorization: Bearer <admin JWT>" -H "Content-Type: application/json" \
        -d '{"kiosk_id": "<kiosk_id>"}'
   ```
   A device belongs to one room; mapping it again moves it. Every mapping and
   unmapping writes a receipt (`voice_device_mapped` / `voice_device_unmapped`,
   with before/after). List: `GET /api/voice-bridge/devices`. Remove:
   `DELETE /api/voice-bridge/devices/<device_id>`.

An unmapped device gets a 404; Home Assistant then says "This speaker isn't
set up with CAOSCare yet" and a `voice_turn_refused` receipt is written.

## 5. Home Assistant setup

1. Copy the integration (section 2) and restart Home Assistant
   (Settings → System → Restart).
2. Settings → Devices & services → Add integration → "CAOSCare conversation
   agent". Enter:
   - Bridge URL: `http://192.168.122.1:<backend port>/api/voice-bridge/turn`
   - Bridge token: the value of `CAOSCARE_VOICE_BRIDGE_TOKEN`
   One entry serves every Voice PE in the community.
3. Speech-to-text and text-to-speech: none are installed yet. Install a local
   STT (e.g. the Whisper add-on via Wyoming) and a local TTS (e.g. Piper), or
   use Home Assistant Cloud. This is a choice for Michael (local vs cloud,
   voice for Aria).
4. Settings → Voice assistants → Add assistant: name "Aria", conversation
   agent **CAOSCare**, the chosen STT and TTS, language English.
5. Open each Voice PE's device page and set its assistant to "Aria".

Home Assistant requirement: the agent uses `ConversationEntity.async_process`
and `ConversationResult(continue_conversation=…)` (Home Assistant 2025.4 or
later). It has not been loaded in Home Assistant yet; check the Home Assistant
log after step 2 for import errors.

## 6. Who owns speech (text-to-speech)

The bridge returns **text**: `response_text` (plain, no markup),
`speech_format: "plain_text"`, `continue_conversation`, `conversation_id`,
`session_id`, `tools_used`, `receipt_id`. It never returns audio and never
calls a TTS service. Home Assistant's Assist pipeline speaks the text with the
TTS engine selected for the "Aria" pipeline, local (e.g. Piper) or cloud
(e.g. Home Assistant Cloud) — switching between them is a Home Assistant
setting and changes nothing in CAOSCare. There is one CAOSCare conversation
path for both.

Existing CAOSCare speech paths are separate and unchanged: the room-screen
Realtime session (speech-to-speech in the browser) and the legacy
`/api/ai/tts` endpoint. The bridge uses neither.

## 7. How a conversation behaves

- Follow-up questions in the same Home Assistant conversation share one
  CAOSCare session (`vb_<conversation id>`), so "What's for dinner?" then
  "What time is that?" keeps context.
- Closing phrases end the session without asking the model and without any
  workflow action: "That'll be all", "That'll be all, Aria", "Goodbye, Aria",
  "I'm done", "Thank you, goodbye" (and close variants, only when that is
  the whole utterance). CAOSCare answers `continue_conversation: false`, so
  the Voice PE returns to wake-word mode, and records a
  `voice_session_ended` receipt. A later turn with the same conversation id
  opens a new session (`…-r2`).
- If Home Assistant resends the same words within 10 seconds (a retry), the
  earlier answer is returned and nothing runs twice
  (`voice_turn_duplicate_ignored` receipt).
- If the model provider fails or the time budget runs out, the resident
  hears a short apology (or, if a request was already filed, that it was
  passed to staff) and a `failed` turn receipt is written. If CAOSCare does
  not answer within 25 s, the Home Assistant agent speaks its own fallback.
- Replies are plain text (no markup), usable for TTS or for display when TTS
  is unavailable.

## 8. Receipts

Every turn writes a receipt (`related_object_type: voice_session`,
`related_object_id: <session id>`): device, resident, room, community,
Home Assistant conversation id, the resident's words, authorization (bridge
credential, device mapping, identity basis `unverified_room_claim`), tools
used, workflow objects (task id + its receipt id), session state before and
after, reply, time, parent receipt and next expected state. Requests keep
their own lifecycle receipts. Read them:
`GET /api/receipts?related_object_type=voice_session&room=<room>` (admin).

## 9. Verification

1. Backend tests: `tests/test_voice_bridge_flow.py`,
   `tests/test_voice_bridge_units.py`, `tests/test_voice_bridge.py`,
   `tests/test_voice_bridge_config.py`.
2. Bridge by hand (no audio), after mapping a test device to a test room:
   ```
   curl -X POST http://192.168.122.1:<port>/api/voice-bridge/turn \
     -H "Authorization: Bearer $CAOSCARE_VOICE_BRIDGE_TOKEN" -H "Content-Type: application/json" \
     -d '{"device_id":"<device_id>","conversation_id":"check1","text":"What is for dinner?"}'
   ```
   Expect `response_text`, `continue_conversation: true`, a `receipt_id`.
   Then send `"text":"That'll be all"` → `continue_conversation: false`.
3. Home Assistant without a Voice PE: Settings → Voice assistants → "Aria"
   → Assist (text). A typed turn has no Voice PE device id, so CAOSCare
   refuses it (404) unless a device id is mapped — expected.
4. Physical Voice PE (not yet done): see the acceptance list in
   `docs/PROJECT_STATE.md` (2026-10-03 bridge readiness entry).

## 10. Rollback

- Stop using the bridge for a room: set the Voice PE's assistant back to the
  previous pipeline (Home Assistant), or `DELETE` its device mapping.
- Stop it everywhere: remove the CAOSCare integration in Home Assistant and/or
  unset `CAOSCARE_VOICE_BRIDGE_TOKEN` and restart the backend (bridge answers
  503).
- Code: the bridge is on `spike/voice-bridge` only; nothing is merged.
  Receipts and conversation records already written stay (history is not
  deleted).
