// RQ-032: request fidelity helpers for the operations tools - kept out of
// realtimeOperationsTools.js. Pure; no server calls.
import { transportStatusMessage } from "./transportation";

const RIDE_OPEN = ["pending", "in_progress"];

// The resident's literal last utterance, sent as resident_words. Very short
// turns ("yes", "okay do that") are confirmations, not a description of the
// request, so they are not stored as the resident's words. The model's own
// summary is always sent separately and is never presented as theirs.
export function literalResidentWords(ctx) {
  const said = String(ctx?.last_user_text || "").trim();
  return said.split(/\s+/).filter(Boolean).length >= 3 ? said.slice(0, 500) : null;
}

// One spoken answer for every open request, each with its own state.
// `data` = /tasks/resident-request/open (everything except transportation);
// `ride` = /transportation/request/status (null when not fetched).
export function openRequestsMessage(data, ride) {
  const items = (data?.found ? data.requests || [] : []).map((d) => {
    const when = d.scheduled_date || d.scheduled_time_label
      ? ` Planned for ${[d.scheduled_time_label, d.scheduled_date].filter(Boolean).join(" on ")}.`
      : "";
    const asked = d.times_asked > 1 ? ` Asked ${d.times_asked} times in all.` : "";
    return `${d.what_for || "a request"} (${d.category}): ${(d.spoken || "").replace(/\.$/, "")}.${when}${asked}`;
  });
  if (ride?.found && RIDE_OPEN.includes(ride.status)) {
    items.push(`your ride (transportation): ${transportStatusMessage(ride).replace(/\.$/, "")}.`);
  }
  const closed = (data?.recently_closed || []).map((d) =>
    `${d.what_for || "a request"} (${d.category}): ${(d.spoken || "").replace(/\.$/, "")}${d.completed_at?.label ? ` (${d.completed_at.label})` : ""}.`);
  const tail = closed.length ? ` Recently finished: ${closed.join(" | ")}` : "";
  if (!items.length) return `you have no open request on record right now.${tail}`;
  const head = items.length === 1 ? "you have 1 open request" : `you have ${items.length} open requests`;
  return `${head}, each with its own state - ${items.join(" | ")}${tail}`;
}

// What Aria may truthfully say right after filing a request. Filing is not the
// department being told, and being told is not anyone coming: the wording
// follows the real notification state (request_delivery.py) and never
// promises that someone is on the way.
const DELIVERY_SAY = {
  delivered: "the department's notice was delivered",
  sent: "the department's notice was sent; delivery is not confirmed yet",
  simulated: "this is a demo request, so no real notice was sent",
  not_sent: "no notice could be sent (no email or text service is set up); it shows on their screen when they look",
  failed: "the notice to the department failed; it shows on their screen when they look",
};
export function newRequestMessage(category, delivery) {
  const told = DELIVERY_SAY[delivery] || "it shows on their screen when they look";
  return `request filed for ${category}: ${told}. No one has seen it yet - do not say anyone is coming or on the way.`;
}
