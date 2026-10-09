import { executeDeviceTool } from "../realtimeDeviceTools";

const ctx = { resident_id: "r1", session_id: "s1", room: "214" };

function mockFetch(status, body) {
  global.fetch = jest.fn(async () => ({ ok: status < 400, status, json: async () => body }));
}

test("sends resident_id and session_id", async () => {
  mockFetch(200, { answer: "a", live: true, source: "openai_web_search", citations: ["https://x"] });
  const r = await executeDeviceTool({ name: "research_topic", args: { question: "q?" }, ctx });
  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body).toMatchObject({ question: "q?", resident_id: "r1", session_id: "s1" });
  expect(r.ok).toBe(true);
});

test.each([403, 429])("%i becomes an honest refusal, not an answer", async (code) => {
  mockFetch(code, { detail: "x" });
  const r = await executeDeviceTool({ name: "research_topic", args: { question: "q?" }, ctx });
  expect(r).toEqual({ ok: false, message: "I can't look that up right now." });
});

test("sends owner token when present", async () => {
  localStorage.setItem("caos_token", "tok");
  mockFetch(200, { answer: "a" });
  await executeDeviceTool({ name: "research_topic", args: { question: "q?" }, ctx: {} });
  expect(global.fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer tok");
  localStorage.removeItem("caos_token");
});
