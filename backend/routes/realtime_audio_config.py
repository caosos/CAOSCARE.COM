"""Realtime session audio config constants - split out of realtime.py to
keep that file from growing past the repo's 300-line cap. Pure data, no
routes or DB access.
"""

# REVERTED 2026-08-23: semantic_vad+low caused a real ~38s speech-detection
# dead zone live (connection healthy throughout, per lifecycle diagnostics -
# a turn-detection failure, not network). Back to the known-working config.
DEFAULT_VAD = {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 1000,
    "create_response": True,
    "interrupt_response": True,
}

# Owner 2026-10-22 ("whys it on hold if its better then lets do it"): the verified owner room (Room 214) waits
# 1.8 s of silence before its turn ends. Michael's 19 resumptions since 10-20 paused 1.0-3.3 s; 1.8 s covers 14
# of them, including rt_qppzkpzp 23:22 (1.73 s); 1.5 s would not. Cost: every reply in that room starts ~0.8 s
# later. Every other room keeps DEFAULT_VAD. Chosen at the verified owner-room mint (realtime_resident_session).
OWNER_ROOM_SILENCE_MS = 1800
OWNER_ROOM_VAD = {**DEFAULT_VAD, "silence_duration_ms": OWNER_ROOM_SILENCE_MS}


def turn_detection_for(owner_room: bool) -> dict:
    return OWNER_ROOM_VAD if owner_room else DEFAULT_VAD


# 2026-08-22: a real acceptance test showed short phantom transcripts
# ("Thank you.", "Cheers, bye.") appearing during genuine silence - VAD
# picking up room/ambient noise, not echo. far_field is OpenAI's own
# documented setting for exactly this (room/tablet/conference-style mics,
# vs near_field for headsets) - confirmed against the current API
# reference, not guessed. Filters audio before VAD/the model see it.
DEFAULT_NOISE_REDUCTION = {"type": "far_field"}
