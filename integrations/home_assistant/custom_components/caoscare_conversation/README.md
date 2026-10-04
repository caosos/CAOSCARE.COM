# CAOSCare conversation agent (not yet run in Home Assistant)

Assist pipeline: Voice PE wake word → Home Assistant speech-to-text →
**this agent** → CAOSCare `POST /api/voice-bridge/turn` → reply text → Home
Assistant text-to-speech. CAOSCare owns the conversation, residents, menus,
activities, requests, permissions and receipts. This agent stores only the
bridge URL and credential; it sends each Voice PE's Home Assistant device id,
and CAOSCare maps that device to its room and resident.

`bridge_client.py` holds the HTTP call (timeouts and errors become a spoken
fallback); it has no Home Assistant imports and is tested in
`backend/tests/test_voice_bridge_units.py`.

Installation, configuration, verification and rollback:
`docs/VOICE_PE_BRIDGE_INSTALL.md`.
