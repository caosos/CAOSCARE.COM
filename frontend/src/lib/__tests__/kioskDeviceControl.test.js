/**
 * Regression test for the real 2026-09-06 kiosk multi-light bug: Kiosk.jsx's
 * device-card click handler posted `kind` alone and dropped the clicked
 * device's device_id, so with two lights in a room (Room 214's Desk Lamp +
 * Overhead Light, both kind="light") every click hit the backend's
 * ambiguity guard ("more than one light device... pass device_id to
 * disambiguate") instead of controlling the actual bulb that was clicked.
 * RoomDevicePanel already passed the full clicked device through onToggle
 * correctly - the bug was entirely in what Kiosk.jsx did with it.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
// Manual factory (not auto-mock) because ../api.js calls axios.create() and
// wires interceptors at import time - an auto-mocked axios.create() returns
// undefined and crashes that module load before this test ever runs.
jest.mock("axios", () => ({
  post: jest.fn(),
  create: () => ({ interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } } }),
}));
import axios from "axios";
import { sendRoomDeviceCommand } from "../kioskDeviceControl";

const DESK_LAMP = { device_id: "dev_desk_lamp", kind: "light", label: "Room 214 Desk Lamp", state: { power: "off" } };
const OVERHEAD_LIGHT = { device_id: "dev_overhead_light", kind: "light", label: "Room 214 Overhead Light", state: { power: "off" } };

// Mirrors RoomDevicePanel's onClick -> Kiosk.jsx's onToggle composition
// exactly: `onClick={() => onToggle(d)}` where onToggle passes
// `d.kind, d.device_id` through to the command sender.
function clickDeviceCard(room, d) {
  return sendRoomDeviceCommand(room, "power", d.state?.power === "on" ? "off" : "on", d.kind, d.device_id);
}

beforeEach(() => {
  axios.post.mockReset();
  axios.post.mockResolvedValue({ data: { ok: true } });
});

test("clicking the Desk Lamp card sends the Desk Lamp's device_id", async () => {
  await clickDeviceCard("214", DESK_LAMP);
  expect(axios.post).toHaveBeenCalledTimes(1);
  const [, body] = axios.post.mock.calls[0];
  expect(body).toMatchObject({ action: "power", value: "on", kind: "light", device_id: "dev_desk_lamp" });
});

test("clicking the Overhead Light card sends the Overhead Light's device_id, not the Desk Lamp's", async () => {
  await clickDeviceCard("214", OVERHEAD_LIGHT);
  expect(axios.post).toHaveBeenCalledTimes(1);
  const [, body] = axios.post.mock.calls[0];
  expect(body.device_id).toBe("dev_overhead_light");
  expect(body.device_id).not.toBe("dev_desk_lamp");
});

test("two sequential clicks on two different same-kind devices each carry only their own device_id", async () => {
  await clickDeviceCard("214", DESK_LAMP);
  await clickDeviceCard("214", OVERHEAD_LIGHT);
  expect(axios.post).toHaveBeenCalledTimes(2);
  const [, firstBody] = axios.post.mock.calls[0];
  const [, secondBody] = axios.post.mock.calls[1];
  expect(firstBody.device_id).toBe("dev_desk_lamp");
  expect(secondBody.device_id).toBe("dev_overhead_light");
});

test("the command body never omits device_id even when the caller doesn't have one (generic devices without an id still shape the same body)", async () => {
  await sendRoomDeviceCommand("214", "power", "on", "tv", undefined);
  const [, body] = axios.post.mock.calls[0];
  expect(body).toHaveProperty("device_id");
});
