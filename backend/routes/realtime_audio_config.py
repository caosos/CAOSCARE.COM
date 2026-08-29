"""Realtime session audio config constants - split out of realtime.py to
keep that file from growing past the repo's 300-line cap. Pure data, no
routes or DB access.
"""

# REVERTED 2026-08-23: semantic_vad+low caused a real ~38s speech-detection
# dead zone live (connection healthy throughout, per lifecycle diagnostics -
# a turn-detection failure, not network). Keep the proven server_vad path.
# 2026-08-29: 1000 -> 700ms because client-side adaptive floor timing now
# adds its own short grace window and cancels a reply if the speaker resumes.
# create_response stays false from mint onward; the browser explicitly sends
# response.create when its adaptive floor controller decides the user yielded.
DEFAULT_VAD = {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 700,
    "create_response": False,
    "interrupt_response": True,
}

# 2026-08-22: a real acceptance test showed short phantom transcripts
# ("Thank you.", "Cheers, bye.") appearing during genuine silence - VAD
# picking up room/ambient noise, not echo. far_field is OpenAI's own
# documented setting for exactly this (room/tablet/conference-style mics,
# vs near_field for headsets) - confirmed against the current API
# reference, not guessed. Filters audio before VAD/the model see it.
DEFAULT_NOISE_REDUCTION = {"type": "far_field"}
