import { executeKioskPreferenceTool } from "../realtimeKioskPreferences";

const ctx = (text = "I don't want that") => ({
  kiosk_id: "k214", resident_id: "r214", room: "214", session_id: "rt_214",
  last_user_text: text, turn_suspect: false,
});

beforeEach(() => { global.fetch = jest.fn(); });

test("an initial opt-out request creates a proposal, not a confirmed write", async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: false, awaiting_confirmation: true, message: "confirm" }) });
  const result = await executeKioskPreferenceTool({ name: "set_tv_audio_duck", args: { enabled: false, confirmed: false }, ctx: ctx() });
  expect(result.awaiting_confirmation).toBe(true);
  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body).toMatchObject({ resident_id: "r214", session_id: "rt_214", enabled: false, confirmed: false, confirmation_text: null, request_text: "I don't want that" });
});

test("the later confirmation sends the resident's exact grounded words", async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true, enabled: false, message: "saved" }) });
  const result = await executeKioskPreferenceTool({ name: "set_tv_audio_duck", args: { enabled: false, confirmed: true }, ctx: ctx("Yes, that's right") });
  expect(result.ok).toBe(true);
  expect(JSON.parse(global.fetch.mock.calls[0][1].body).confirmation_text).toBe("Yes, that's right");
});

test("a suspect turn or missing live-room identity cannot write", async () => {
  expect((await executeKioskPreferenceTool({ name: "set_tv_audio_duck", args: {}, ctx: { ...ctx(), turn_suspect: true } })).ok).toBe(false);
  expect((await executeKioskPreferenceTool({ name: "set_tv_audio_duck", args: {}, ctx: {} })).ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});
