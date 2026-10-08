// Demo room view model: turns the demo room's SmartDevice records (the same
// /devices/public/by-room/{room} list Aria's tools read and write) into what
// the demo room visual draws. No state of its own - the visual only ever
// shows what the device store says, so it can't claim a change that didn't
// happen. Kinds without a device come back null and are drawn as "not set up".

export const DEMO_POLL_MS = 1000;

function firstOfKind(devices, kind) {
  return (devices || []).find((d) => d.kind === kind && d.online !== false) || null;
}

export function demoRoomView(devices) {
  const light = firstOfKind(devices, "light");
  const thermostat = firstOfKind(devices, "thermostat");
  const tv = firstOfKind(devices, "tv");
  const blinds = firstOfKind(devices, "blinds");
  return {
    light: light && {
      on: light.state?.power === "on",
      brightness: typeof light.state?.brightness === "number" ? light.state.brightness : 100,
    },
    thermostat: thermostat && {
      on: thermostat.state?.power !== "off",
      temperature: typeof thermostat.state?.temperature === "number" ? thermostat.state.temperature : null,
    },
    tv: tv && {
      on: tv.state?.power === "on",
      volume: tv.state?.volume ?? null,
      channel: tv.state?.channel ?? null,
      input: tv.state?.input ?? null,
    },
    blinds: blinds && {
      position: typeof blinds.state?.position === "number" ? blinds.state.position : 0,
    },
  };
}

// Short plain-language line per device, for the caption under the visual.
export function demoRoomCaption(view) {
  const parts = [];
  if (view.light) parts.push(`Light ${view.light.on ? `on (${view.light.brightness}%)` : "off"}`);
  if (view.thermostat) parts.push(view.thermostat.on && view.thermostat.temperature != null
    ? `Thermostat ${view.thermostat.temperature}°F` : "Thermostat off");
  if (view.tv) parts.push(view.tv.on
    ? `TV on${view.tv.channel != null ? `, channel ${view.tv.channel}` : ""}${view.tv.volume != null ? `, volume ${view.tv.volume}` : ""}`
    : "TV off");
  if (view.blinds) parts.push(view.blinds.position <= 0 ? "Blinds closed"
    : view.blinds.position >= 100 ? "Blinds open" : `Blinds ${view.blinds.position}% open`);
  return parts;
}

// "Staff notified" chips for the demo room visual. Derived only from the
// resident's real open requests (GET /tasks/resident-request/mine - the same
// StaffTask records the Requests panel and Aria's status answers use); the
// wording follows the request's actual stage and never promises that anyone
// is on the way. Closed requests produce no chip.
export function staffNotifiedChips(requests) {
  return (requests || [])
    .filter((t) => t && t.is_open !== false && (t.status === "pending" || t.status === "in_progress"))
    .map((t) => {
      const stage = t.status === "in_progress" ? "Staff are working on it"
        : t.acknowledged ? "Staff have seen it" : "Staff notified";
      return { id: t.task_id, label: `${stage}: ${t.what_for || t.category || "request"}`, stage };
    });
}
