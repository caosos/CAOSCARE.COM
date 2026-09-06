import axios from "axios";
import { API } from "./api";

// Real bug, 2026-09-06: Kiosk.jsx's device-card click handler, and its own
// TV/speaker auto-mute + restore-on-hangup calls, all POSTed `kind` alone
// and dropped the exact clicked/muted device's device_id - harmless with
// one device per kind, silently ambiguous the moment a room gets a second
// light/TV/etc (backend correctly fails closed: "more than one light
// device... pass device_id to disambiguate"). Extracted out of Kiosk.jsx
// (614 lines, already over the size cap) so this is the one place that
// builds this POST body, and so it's unit-testable without mounting the
// whole kiosk page.
export async function sendRoomDeviceCommand(room, action, value, kind, deviceId) {
  return axios.post(`${API}/devices/public/room/${room}/command`, {
    action, value, kind, device_id: deviceId,
  });
}
