# CAOSCare conversation agent (spike — not installed, not tested in Home Assistant)

Assist pipeline: Voice PE wake word ("Okay Nabu") → HA speech-to-text →
**this agent** → CAOSCare `POST /api/voice-bridge/turn` → reply text → HA
text-to-speech. CAOSCare owns the conversation, memory, menus, activities,
requests, permissions and receipts; this agent holds only the bridge URL,
the bridge credential and the room endpoint id.

This is Home Assistant's staged path (STT → text → TTS), not CAOSCare's
realtime speech-to-speech session.

Before use: an STT engine and a TTS engine in the HA pipeline; one config
entry per room endpoint; a pipeline per room selecting this agent; the
Voice PE assigned to that pipeline. `continue_conversation` requires a
Home Assistant version that supports it.
