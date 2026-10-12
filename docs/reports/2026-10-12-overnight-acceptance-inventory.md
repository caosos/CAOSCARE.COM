# Overnight acceptance — what exists today (read-only inventory, 2026-10-12 ~01:15 CDT)

For the owner authorization relayed in #129 comment 6118737780. The live switch itself was **not** made: this session's permission check refused to act on a relayed authorization for a paid, live Room 214 change (BLOCKED receipt #6118763661). Room 214 is unchanged (backend `e5c516a`, `gpt-realtime`/`shimmer`, new flags off, listener untouched).

| Acceptance item | What exists now | Missing dependency (exact) |
|---|---|---|
| 1. Personality + quick-return | code ready (`CAOSCARE_CONTINUITY_RECENT_MINUTES`, model/voice settings) | Michael's go-ahead in the coordinator session for the live switch and test calls |
| 2. Live lookup | research route built (RQ-047) | `CAOSCARE_RESEARCH_PROVIDER` and `OPENAI_RESEARCH_MODEL` unset; go-ahead for paid lookups |
| 3. Music | **no `media_player` entity in Home Assistant** (domains present: light, climate, switch, fan, sensor, weather, tts, notify, todo, …) | a connected speaker/media player in Home Assistant |
| 4. Alexa-class room functions | lights: 2 Home Assistant bulbs (desk lamp off, overhead on); weather: HA `weather` + CAOSCare `get_weather`; timers: CAOSCare `set_timer`; thermostat: `climate.bedroom_midea_ac` **unavailable** | the Midea AC is offline in Home Assistant |
| 5. Calls | honest `call_contact` built (default off) | Asterisk not installed; no Twilio/SIP account configured |
| 6. Bathroom → Nursing → nurse email | request + Nursing queue work (DEV_ACCEPTED earlier) | `RESEND_API_KEY` unset: no real email can be sent, only recorded |
| 7. SIMs | Live Operations controls built (SIM-1..4) | — (can be exercised once the run is wanted; development only) |
| 8. Resident + staff walkthrough | screens built and browser-checked tonight | Claude-in-Chrome firsthand run pending the go-ahead |
