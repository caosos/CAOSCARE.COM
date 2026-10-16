// Spoken room status for Aria's get_room_status tool. Split out of
// realtimeDeviceTools.js (2026-10-16, aria-room-runtime-fixes-001) when the
// tool moved onto the server's room inventory.
import { nearestColorName, colorTempLabel } from "./realtimeLightControl";

// One human-readable sentence per device, driven entirely by that device's
// OWN declared capabilities/state - not a hardcoded thermostat/TV special
// case - so a light, fan, or blinds device registered later is described
// correctly without a code change here. Shared logic for get_room_status
// (spoken) - the resident-facing device panel builds its own visual cards
// from the same raw device list, not this sentence.
export function describeDevice(d) {
  const s = d.state || {};
  const caps = d.capabilities || [];
  const name = d.room ? d.label.replace(`Room ${d.room} `, "") : d.label;
  if (d.online === false) return `the ${name} is offline`;
  const bits = [];
  if (caps.includes("power")) bits.push(s.power === "on" ? "on" : "off");
  if (caps.includes("temperature") && typeof s.temperature === "number") bits.push(`set to ${s.temperature} degrees`);
  if (caps.includes("input") && s.input) bits.push(`on ${s.input}`);
  // One-way IR state is the last command/estimate, not a device observation.
  // Never speak that number as though the TV reported it. A state-reporting
  // adapter may expose a numeric volume without volume_estimated.
  if (caps.includes("volume") && typeof s.volume === "number" && s.power === "on"
      && d.protocol !== "ir_blaster" && s.volume_estimated !== true) bits.push(`volume ${s.volume}`);
  if (caps.includes("brightness") && typeof s.brightness === "number" && s.power === "on") bits.push(`brightness ${s.brightness}`);
  if (caps.includes("color") && s.color && s.power === "on") {
    const name = nearestColorName(s.color);
    if (name) bits.push(name);
  }
  if (caps.includes("color_temp") && s.color_temp && s.power === "on") {
    const label = colorTempLabel(s.color_temp);
    if (label) bits.push(label);
  }
  if (caps.includes("fan_speed") && s.fan_speed != null) bits.push(`fan speed ${s.fan_speed}`);
  if (caps.includes("position") && s.position != null) bits.push(`position ${s.position}`);
  if (!bits.length) return null;
  return `the ${name} is ${bits.join(", ")}`;
}

// get_room_status speaks from the server's room inventory
// (backend/routes/room_device_inventory.py): readings only from devices whose
// transport reports state, then what is connected, what each can do, and what
// this room does not have.
export function roomStatusResult(inv) {
  const readings = (inv.connected || [])
    .filter((c) => c.reported_state && Object.keys(c.reported_state).length)
    .map((c) => describeDevice({ label: c.name, capabilities: c.capabilities, state: c.reported_state, protocol: c.protocol }))
    .filter(Boolean);
  const reading = readings.length ? `Current readings: ${readings.join("; ")}. ` : "";
  return {
    ok: true,
    message: reading + (inv.summary || ""),
    connected: (inv.connected || []).map((c) => ({ name: c.name, kind: c.kind, actions: c.actions, state_feedback: c.state_feedback })),
    not_connected: inv.not_connected || [],
  };
}
