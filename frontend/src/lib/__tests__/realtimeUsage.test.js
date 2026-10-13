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
  expect(sanitizeRealtimeUsage({ input_tokens: -2, output_tokens: "9" })).toMatchObject({ input_tokens: 0, output_tokens: 0 });
  expect(sanitizeRealtimeUsage(null)).toBeNull();
});
