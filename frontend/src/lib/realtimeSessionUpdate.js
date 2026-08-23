/**
 * Builds the session.update payload sent once the data channel opens.
 * Split out of useRealtimeVoice.js 2026-08-23 to keep that file under the
 * repo's 300-line cap - pure data construction, no behavior change.
 *
 * FIXED 2026-08-09 (real, confirmed live error, seen on screen: "Missing
 * required parameter: 'session.type'"): the current Realtime API requires
 * `type: "realtime"` INSIDE the session object on every session.update
 * event, same as the mint-time session_config already has server-side.
 * Without it, OpenAI rejected every update - which is where tools/
 * turn_detection/temperature get applied, so the live call had correct
 * instructions (from mint) but NONE of those, silently, until the
 * resulting error surfaced in the UI.
 *
 * voice, input_audio_transcription, and turn_detection all live under
 * nested audio.output/audio.input, NOT flat top-level session fields, in
 * the current Realtime API - confirmed via a real end-to-end connection
 * test (aiortc, full ICE/DTLS handshake, not just SDP exchange) that
 * returned "Unknown parameter" errors one at a time for each flat field
 * until corrected. session.type is also required (separately confirmed
 * live, on-screen, as "Missing required parameter: 'session.type'").
 *
 * REMOVED 2026-08-22: a top-level `include` field here was rejected live
 * ("Unknown parameter: 'include'"), likely voiding the whole
 * session.update - the same test's missing user transcripts. Removed,
 * not relocated by guess; transcriptionConfidence() safely no-ops with no
 * logprobs, so the trust boundary still runs on the audio-overlap signal
 * alone.
 *
 * temperature is NOT a valid session.update field in the current API
 * ("Unknown parameter: 'session.temperature'", confirmed live) - dropped
 * rather than guessing at a new location, since it's not audio-related
 * like the other three fields that just moved.
 */
export function buildSessionUpdate({ caos, voice }) {
  const update = {
    type: "session.update",
    session: {
      type: "realtime",
      instructions: caos.instructions,
      audio: {
        output: { voice: caos.voice || voice },
        input: {
          // 2026-08-22: whisper-1 -> gpt-4o-transcribe (confirmed valid in
          // this exact field for a normal realtime conversational session).
          // Real Room 102 evidence showed correctly-bounded turns with
          // wrong recognized words (VAD wasn't the problem); gpt-4o-transcribe
          // is documented to improve recognition accuracy over whisper-1.
          transcription: { model: "gpt-4o-transcribe", language: "en" },
          ...(caos.noise_reduction ? { noise_reduction: caos.noise_reduction } : {}),
          ...(caos.turn_detection ? { turn_detection: { ...caos.turn_detection, create_response: false } } : {}),
        },
      },
    },
  };
  if (caos.tools) update.session.tools = caos.tools;
  if (caos.tool_choice) update.session.tool_choice = caos.tool_choice;
  return update;
}
