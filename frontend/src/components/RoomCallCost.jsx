import React from "react";

function dollars(value) {
  if (value === null || value === undefined) return null;
  if (value === 0) return "$0.0000";
  return value < 0.0001 ? `<$0.0001` : `$${value.toFixed(4)}`;
}

export function roomCallCostLabel(call) {
  if (!call) return "Call cost unavailable";
  if (call.call_status === "no_call") return "No call receipt";
  const scope = call.environment === "development_test" ? "Test call" : "Last call";
  const state = call.call_status === "failed" ? " · failed" : "";
  if (call.estimate_status === "complete") return `${scope} estimated ${dollars(call.estimated_usd)}${state}`;
  if (call.estimate_status === "incomplete" && call.known_estimated_usd !== null) {
    return `${scope} at least ${dollars(call.known_estimated_usd)} · incomplete usage${state}`;
  }
  return `${scope} cost unknown · usage unavailable${state}`;
}

export default function RoomCallCost({ call, room }) {
  return (
    <div className="mt-1 text-[11px] leading-snug text-caos-mute" data-testid={`room-call-cost-${room}`}>
      {roomCallCostLabel(call)}
    </div>
  );
}
