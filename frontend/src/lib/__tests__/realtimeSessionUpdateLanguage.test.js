/**
 * Terminal 10 (conversation parity) regression: the resident-facing
 * session.update must not force English transcription.
 *
 * Verified against current OpenAI Realtime API docs (2026-09-10): a full
 * conversational session (session.type: "realtime") only accepts
 * gpt-4o-transcribe / gpt-4o-mini-transcribe / whisper-1 as
 * input_audio_transcription.model, and those use a singular, OPTIONAL
 * `language` hint - omitting it lets the model auto-detect the spoken
 * language per turn. The multi-language `languages` array belongs to
 * gpt-transcribe/gpt-live-transcribe, which only work inside a dedicated
 * session.type:"transcription" session (not this one), so this file does
 * NOT swap models or invent an unsupported field - it only stops
 * hard-coding English.
 */
import { buildSessionUpdate } from "../realtimeSessionUpdate";

function build(overrides = {}) {
  return buildSessionUpdate({
    caos: { instructions: "test instructions", voice: "alloy", ...overrides },
    voice: "alloy",
  });
}

test("does not force English transcription", () => {
  const update = build();
  const transcription = update.session.audio.input.transcription;
  expect(transcription.model).toBe("gpt-4o-transcribe");
  expect(transcription).not.toHaveProperty("language");
});

test("does not send the unsupported multi-language field for this model", () => {
  // Guard against a future edit re-introducing a guessed field: gpt-4o-transcribe
  // does not accept `languages` (plural) - only gpt-transcribe/gpt-live-transcribe
  // do, and only in a dedicated transcription session.
  const update = build();
  expect(update.session.audio.input.transcription).not.toHaveProperty("languages");
});

test("session.type and required realtime fields are still present", () => {
  // Regression guard for the 2026-08-09 "Missing required parameter:
  // 'session.type'" live incident - the language fix must not disturb it.
  const update = build();
  expect(update.session.type).toBe("realtime");
  expect(update.type).toBe("session.update");
  expect(update.session.audio.output.voice).toBe("alloy");
});

test("noise_reduction and turn_detection still pass through unaffected", () => {
  const update = buildSessionUpdate({
    caos: {
      instructions: "x", voice: "alloy",
      noise_reduction: { type: "far_field" },
      turn_detection: { type: "server_vad", threshold: 0.5 },
    },
    voice: "alloy",
  });
  const input = update.session.audio.input;
  expect(input.noise_reduction).toEqual({ type: "far_field" });
  expect(input.turn_detection).toEqual({ type: "server_vad", threshold: 0.5, create_response: false });
});
