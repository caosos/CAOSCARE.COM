import { sanitizeRealtimeUsage } from "../realtimeDiagnostics";

test("keeps only nonnegative numerical realtime usage counters", () => {
  const got = sanitizeRealtimeUsage({
    total_tokens: 30, input_tokens: 20, output_tokens: 10,
    input_token_details: { text_tokens: 3, audio_tokens: 17, cached_tokens: 5,
      cached_tokens_details: { text_tokens: 1, audio_tokens: 4 }, secret: "drop" },
    output_token_details: { text_tokens: 2, audio_tokens: 8, transcript: "drop" },
    output: [{ content: "never persist" }],
  });
  expect(got).toEqual({
    total_tokens: 30, input_tokens: 20, output_tokens: 10,
    input_token_details: { text_tokens: 3, audio_tokens: 17, cached_tokens: 5,
      cached_tokens_details: { text_tokens: 1, audio_tokens: 4 } },
    output_token_details: { text_tokens: 2, audio_tokens: 8 },
  });
  expect(JSON.stringify(got)).not.toContain("persist");
  // Invalid or missing counters are unknown (null), never a silent 0 that would read as "free".
  expect(sanitizeRealtimeUsage({ input_tokens: -2, output_tokens: "9" })).toMatchObject({
    input_tokens: null, output_tokens: null, total_tokens: null,
    input_token_details: { text_tokens: null, cached_tokens_details: { audio_tokens: null } },
  });
  expect(sanitizeRealtimeUsage(null)).toBeNull();
});

test("transcription usage is forwarded with the provider's counters, unknown ones null, and never the transcript", () => {
  const { logTranscriptionUsage } = require("../realtimeDiagnostics");
  const sent = [];
  global.fetch = jest.fn((url, opts) => { sent.push(JSON.parse(opts.body)); return Promise.resolve({}); });
  logTranscriptionUsage("rt_1", { item_id: "item_9", transcript: "private words",
    usage: { type: "tokens", input_tokens: 40, output_tokens: 6, input_token_details: { audio_tokens: 38 } } }, "gpt-4o-transcribe");
  logTranscriptionUsage("rt_1", { item_id: "item_10", transcript: "more words" }, "gpt-4o-transcribe");
  expect(sent[0]).toMatchObject({ session_id: "rt_1", event_type: "transcription_usage", response_id: "item_9",
    meta: { model: "gpt-4o-transcribe", provider: "openai",
      usage: { type: "tokens", input_tokens: 40, output_tokens: 6, total_tokens: null,
        input_token_details: { audio_tokens: 38, text_tokens: null } } } });
  expect(sent[1].meta.usage).toBeNull();
  expect(JSON.stringify(sent)).not.toContain("words");
});
