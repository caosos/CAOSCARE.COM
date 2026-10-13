import { executeDeviceTool } from "../realtimeDeviceTools";

beforeEach(() => { global.fetch = jest.fn(); });

test("voice TV setup sends authoritative session context and the resident's confirmation words", async () => {
  fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true, setup_id: "s1", message: "test ready" }) });
  const result = await executeDeviceTool({
    name: "configure_tv_remote",
    args: { phase: "test", setup_id: "s1" },
    ctx: { room: "214", resident_id: "res1", session_id: "sid1", last_user_text: "Yes, go ahead", turn_suspect: false },
  });
  expect(result.ok).toBe(true);
  const sent = JSON.parse(fetch.mock.calls[0][1].body);
  expect(sent).toMatchObject({ phase: "test", resident_id: "res1", session_id: "sid1",
    setup_id: "s1", confirmation_text: "Yes, go ahead", turn_suspect: false });
});

test("suspect voice turn is refused before remote setup changes anything", async () => {
  const result = await executeDeviceTool({
    name: "configure_tv_remote", args: { phase: "confirm", setup_id: "s1", worked: true },
    ctx: { room: "214", resident_id: "res1", session_id: "sid1", last_user_text: "yes", turn_suspect: true },
  });
  expect(result.ok).toBe(false);
  expect(fetch).not.toHaveBeenCalled();
});
