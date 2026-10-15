import { executeSelfCodeTool, SELF_CODE_TOOLS } from "../realtimeSelfCodeTools";

const ctx = { resident_id: "res214", session_id: "rt_214", room: "214" };

function mockFetch(status, body) {
  global.fetch = jest.fn(async () => ({ ok: status < 400, status, json: async () => body }));
}

test("ignores names it does not own", async () => {
  expect(await executeSelfCodeTool({ name: "toggle_tv", args: {}, ctx })).toBeUndefined();
  expect(Object.keys(SELF_CODE_TOOLS)).toEqual(["inspect_own_code", "search_own_code", "read_own_code"]);
});

test("sends only the session's own identity, never a model-supplied room", async () => {
  mockFetch(200, { ok: true, message: "m" });
  await executeSelfCodeTool({ name: "inspect_own_code", args: { room: "214", resident_id: "someone" }, ctx });
  const [url, init] = global.fetch.mock.calls[0];
  expect(url).toMatch(/\/api\/aria\/self-code\/inspect$/);
  const body = JSON.parse(init.body);
  expect(body).toEqual({ session_id: "rt_214", resident_id: "res214", frontend_build_sha: null });
  expect(init.headers.Authorization).toBeUndefined();
});

test("read passes a bounded range and search passes the query", async () => {
  mockFetch(200, { ok: true });
  await executeSelfCodeTool({ name: "read_own_code", args: { path: "backend/routes/aria_life_memory.py", start_line: 10, end_line: 40 }, ctx });
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toMatchObject({ path: "backend/routes/aria_life_memory.py", start_line: 10, end_line: 40 });
  await executeSelfCodeTool({ name: "read_own_code", args: { path: "x.py", start_line: -3 }, ctx });
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toMatchObject({ path: "x.py", start_line: 1 });
  await executeSelfCodeTool({ name: "search_own_code", args: { query: "life_story" }, ctx });
  expect(global.fetch.mock.calls[2][0]).toMatch(/\/search$/);
  expect(JSON.parse(global.fetch.mock.calls[2][1].body).query).toBe("life_story");
});

test("a 403 from the gate becomes an honest refusal, not an answer", async () => {
  mockFetch(403, { detail: { reason: "not_room_214" } });
  const r = await executeSelfCodeTool({ name: "inspect_own_code", args: {}, ctx });
  expect(r.ok).toBe(false);
  expect(r.refused).toBe(true);
  expect(r.message).toMatch(/only available to the verified Room 214 session/);
  mockFetch(403, { detail: { reason: "path_not_approved" } });
  expect((await executeSelfCodeTool({ name: "read_own_code", args: { path: "backend/.env" }, ctx })).message).toMatch(/outside what I'm allowed to read/);
});

test("other failures are reported, never invented", async () => {
  mockFetch(502, {});
  expect((await executeSelfCodeTool({ name: "search_own_code", args: { query: "x" }, ctx })).ok).toBe(false);
});
