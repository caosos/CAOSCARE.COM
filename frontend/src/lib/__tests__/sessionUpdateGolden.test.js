/**
 * Test-reality gap 4: a golden check of the session.update sent when the data
 * channel opens. It catches an accidental field change or a re-introduction of a
 * field the provider already rejected live (2026-08-09 / 08-22): flat voice/
 * turn_detection/input_audio_transcription, top-level include, session.temperature.
 * It is NOT provider acceptance; that needs one owner-approved live call.
 */
import { buildSessionUpdate } from "../realtimeSessionUpdate";

const caos = {
  instructions: "INSTR", voice: "marin",
  tools: [{ type: "function", name: "end_call" }], tool_choice: "auto",
  turn_detection: { type: "server_vad", threshold: 0.5, prefix_padding_ms: 300, silence_duration_ms: 1000, create_response: true, interrupt_response: true },
  noise_reduction: { type: "far_field" }, temperature: 0.8,
};

test("exact golden shape", () => {
  expect(buildSessionUpdate({ caos, voice: "alloy" })).toEqual({
    type: "session.update",
    session: {
      type: "realtime",
      instructions: "INSTR",
      audio: {
        output: { voice: "marin" },
        input: {
          transcription: { model: "gpt-4o-transcribe" },
          noise_reduction: { type: "far_field" },
          // create_response is held off until the greeting finishes (re-enabled by the gate)
          turn_detection: { type: "server_vad", threshold: 0.5, prefix_padding_ms: 300, silence_duration_ms: 1000, create_response: false, interrupt_response: true },
        },
      },
      tools: [{ type: "function", name: "end_call" }],
      tool_choice: "auto",
    },
  });
});

test("fields the provider rejected live never come back", () => {
  const u = buildSessionUpdate({ caos, voice: "alloy" });
  const s = u.session;
  for (const k of ["include", "temperature", "voice", "turn_detection", "input_audio_transcription"]) expect(s).not.toHaveProperty(k);
  expect(u).not.toHaveProperty("include");
  expect(s.type).toBe("realtime");
});

test("the transcription language is not pinned by default (auto-detect)", () => {
  expect(buildSessionUpdate({ caos, voice: "alloy" }).session.audio.input.transcription).not.toHaveProperty("language");
});
