// check_appointment / note_reported_appointment relay the backend's truthful
// line through the real tool dispatcher (aria-appointment-verification-001).
import { executeCareTool } from "../realtimeCareControl";

const CTX = { room: "214", resident_id: "res_1", session_id: "rt_1", last_user_text: "I think my cardiologist is Tuesday at 10" };

afterEach(() => { delete global.fetch; });

test("note_reported_appointment sends what the resident said and relays REPORTED, never verified", async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({
    ok: true, recorded: true, status: "REPORTED", verified: false, receipt_id: "rcpt_1",
    spoken: "I have your cardiologist appointment on Tuesday, October 20 at 10 AM, from what you told me today. It isn't verified yet - there's no confirmation on file." }) }));
  const r = await executeCareTool({ name: "note_reported_appointment",
    args: { provider: "cardiologist", date: "2026-10-20", time: "10:00", time_as_said: "at 10" }, ctx: CTX });
  expect(global.fetch.mock.calls[0][0]).toMatch(/\/appointments\/public\/report$/);
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({
    resident_id: "res_1", room: "214", provider: "cardiologist", date: "2026-10-20", time: "10:00",
    time_as_said: "at 10", location: null, says_changed: false,
    resident_words: "I think my cardiologist is Tuesday at 10", conversation_session_id: "rt_1" });
  expect(r).toMatchObject({ ok: true, recorded: true, status: "REPORTED", verified: false, receipt_id: "rcpt_1" });
  expect(r.message).toMatch(/isn't verified yet/);
});

test("check_appointment passes the question's focus and relays the verified time with the discrepancy", async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({
    ok: true, found: true, appointments: [{ status: "VERIFIED", verified: true }],
    spoken: "Your cardiologist appointment is Tuesday, October 20 at 10:30 AM. That's verified by the confirmation email received on October 14. You'd told me 10 AM, but the confirmation says 10:30 AM." }) }));
  const r = await executeCareTool({ name: "check_appointment", args: { about: "cardiologist", focus: "time" }, ctx: CTX });
  expect(global.fetch.mock.calls[0][0]).toMatch(/\/appointments\/public\/check$/);
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual(
    { resident_id: "res_1", room: "214", about: "cardiologist", date: null, focus: "time" });
  expect(r.message).toMatch(/10:30 AM/);
  expect(r.appointments[0].verified).toBe(true);
});

test("a failed call says nothing is known or saved, and no room context is refused", async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 500 }));
  const c = await executeCareTool({ name: "check_appointment", args: {}, ctx: CTX });
  expect(c).toMatchObject({ ok: false });
  expect(c.message).toMatch(/can't tell you what's on file/);
  const n = await executeCareTool({ name: "note_reported_appointment", args: { date: "2026-10-20" }, ctx: CTX });
  expect(n.message).toMatch(/nothing was recorded/);
  global.fetch = jest.fn();
  const none = await executeCareTool({ name: "check_appointment", args: {}, ctx: {} });
  expect(none.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});
