/**
 * Tool dispatch for the operational request bus (staff requests,
 * transportation, schedule, menu) - split out of useRealtimeVoice.js
 * 2026-08-10, which had grown well past the repo's 400-line code-file
 * cap. Same dispatch contract as the parent's executeTool(): returns
 * `{ ok, message, ... }` for names it handles, or `undefined` for
 * anything else so the caller can fall through to its own dispatch.
 */
import { API } from "./api";

// 2026-08-23: the backend rejects an operational mutation (422 +
// needs_clarification) when a free-text field claims a fact - so far only
// a clock time - the resident never actually stated this session (Room
// 304's fabricated "10 o'clock" reaching a real staff task). Surface that
// as a natural spoken question instead of the generic "couldn't send that
// request" failure, so the model asks rather than silently retrying with
// the same invented detail.
async function needsClarificationMessage(r) {
  if (r.status !== 422) return null;
  try {
    const body = await r.json();
    const reason = body?.detail?.reason;
    if (body?.detail?.needs_clarification && reason) {
      return `I don't have that confirmed - ${reason}. Could you tell me the actual time?`;
    }
  } catch {}
  return null;
}

export async function executeOperationsTool({ name, args, ctx }) {
  const { room, residentId, sessionId, turnSuspect, turnSuspectReason } = ctx;
  // 2026-08-23: "echo_like" genuinely suggests mishearing - ask to repeat.
  // Other suspect reasons read better as a quick confirmation, not "I
  // misheard you" - see realtimeMessageHandler.js's classifyUserTurn().
  const suspectMsg = turnSuspectReason === "echo_like"
    ? "I want to make sure I heard that right — could you say that again?"
    : "Just to double-check — is that what you'd like me to do?";

  if (name === "request_staff_help" && turnSuspect) {
    // The turn that triggered this looked like it might not be genuine
    // resident speech (echo/noise-hallucination signal) - don't file a
    // real staff ticket over words nobody may have actually said.
    return { ok: false, message: suspectMsg };
  }

  if (name === "request_staff_help") {
    const r = await fetch(`${API}/tasks/resident-request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: args.category,
        resident_id: residentId || null,
        room: room || null,
        resident_words: args.summary || null,
        summary: args.summary || "Resident request",
        priority: args.priority || "normal",
        source: "aria_voice",
        conversation_session_id: sessionId || null,
      }),
    });
    if (!r.ok) {
      const clarify = await needsClarificationMessage(r);
      return { ok: false, message: clarify || `couldn't send that request (${r.status}) - please try the call button instead.` };
    }
    const data = await r.json();
    if (data.duplicate) {
      // 2026-08-27: the existing open ticket may be about a DIFFERENT
      // problem than what was just asked (same category, different issue) -
      // say what it's actually about instead of implying it's the same one.
      const aboutClause = data.same_issue || !data.existing_summary
        ? "this"
        : `something else already open in ${args.category} ("${data.existing_summary}")`;
      return {
        ok: true,
        message: `there's already an open ${args.category} request on file for ${aboutClause} - I've let them know again (this is ask #${data.re_request_count}), current status: ${data.status}.`,
        task_id: data.task_id,
      };
    }
    return { ok: true, message: `request created (${data.status}) and sent to ${args.category}.`, task_id: data.task_id };
  }

  if (name === "check_request_status") {
    const qs = new URLSearchParams();
    if (residentId) qs.set("resident_id", residentId);
    else if (room) qs.set("room", room);
    else qs.set("conversation_session_id", sessionId || "");
    if (args.category) qs.set("category", args.category);
    const r = await fetch(`${API}/tasks/resident-request/status?${qs.toString()}`);
    if (!r.ok) return { ok: false, message: `couldn't check that (${r.status}).` };
    const data = await r.json();
    if (!data.found) return { ok: true, message: "no matching request found on record." };
    const scheduleClause = data.scheduled_date || data.scheduled_time_label
      ? `planned for ${[data.scheduled_time_label, data.scheduled_date].filter(Boolean).join(" on ")}`
      : "no scheduled time yet";
    const parts = [
      `it's for ${data.what_for || "something you asked about"}`,
      `status: ${data.status}${data.acknowledged ? " (acknowledged)" : " (not yet acknowledged)"}${data.assigned_to_name ? `, assigned to ${data.assigned_to_name}` : ""}`,
      scheduleClause,
    ];
    if (data.latest_update) parts.push(`latest update: ${data.latest_update.replace(/\.$/, "")}`);
    return { ok: true, message: parts.join("; ") + "." };
  }

  if (name === "check_transportation_availability") {
    // Resource-aware (driver+vehicle) - the same engine request_transportation
    // actually books against, so this can never promise an opening the
    // booking call then can't honor.
    const qs = args.date ? `?date=${encodeURIComponent(args.date)}` : "";
    const r = await fetch(`${API}/transportation/availability/public${qs}`);
    if (!r.ok) return { ok: false, message: `couldn't check availability (${r.status}).` };
    const slots = await r.json();
    const open = slots.filter((s) => s.open);
    if (!open.length) return { ok: true, message: "no open transportation times found for that date." };
    return { ok: true, message: `open times: ${open.map((s) => s.start_time).join(", ")}.` };
  }

  if (name === "request_transportation" && turnSuspect) {
    return { ok: false, message: suspectMsg };
  }

  if (name === "request_transportation") {
    const r = await fetch(`${API}/transportation/request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resident_id: residentId || null,
        room: room || null,
        purpose: args.purpose,
        requested_for_date: args.requested_for_date,
        requested_for_time_label: args.requested_for_time_label || null,
        start_time: args.start_time || null,
        source: "aria_voice",
        conversation_session_id: sessionId || null,
      }),
    });
    if (!r.ok) {
      const clarify = await needsClarificationMessage(r);
      return { ok: false, message: clarify || `couldn't send that request (${r.status}) - please try the call button instead.` };
    }
    const data = await r.json();
    if (data.duplicate) {
      return { ok: true, message: `there's already an open transportation request on file for ${data.status === "pending" ? "that date" : data.status} - I've flagged it again (ask #${data.re_request_count}).` };
    }
    if (!data.booked) {
      return { ok: true, message: `request submitted for ${args.requested_for_date} - the front desk needs to coordinate the time, no confirmed time yet.` };
    }
    const sharedNote = data.shared ? " you'll be riding with another resident on the same trip." : "";
    return { ok: true, message: `confirmed - your ride is booked for ${data.run.depart_time} on ${args.requested_for_date}.${sharedNote}` };
  }

  if (name === "check_transportation_status") {
    const qs = new URLSearchParams();
    if (residentId) qs.set("resident_id", residentId);
    else if (room) qs.set("room", room);
    else qs.set("conversation_session_id", sessionId || "");
    const r = await fetch(`${API}/transportation/request/status?${qs.toString()}`);
    if (!r.ok) return { ok: false, message: `couldn't check that (${r.status}).` };
    const data = await r.json();
    if (!data.found) return { ok: true, message: "no transportation request found on record." };
    return {
      ok: true,
      message: data.booked
        ? `booked for ${data.slot?.start_time} on ${data.requested_for_date}.`
        : `still waiting - requested for ${data.requested_for_date}, no confirmed time yet.`,
    };
  }

  if (name === "change_transportation_request") {
    const r = await fetch(`${API}/transportation/request/change-mine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resident_id: residentId || null,
        room: room || null,
        conversation_session_id: sessionId || null,
        requested_for_date: args.requested_for_date,
        requested_for_time_label: args.requested_for_time_label || null,
        start_time: args.start_time || null,
      }),
    });
    if (!r.ok) return { ok: false, message: `couldn't change that (${r.status}).` };
    const data = await r.json();
    return {
      ok: true,
      message: data.booked
        ? `changed and confirmed for ${data.slot.start_time} on ${args.requested_for_date}.`
        : `changed to ${args.requested_for_date} - no confirmed time yet.`,
    };
  }

  if (name === "cancel_transportation_request") {
    const r = await fetch(`${API}/transportation/request/cancel-mine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resident_id: residentId || null, room: room || null, conversation_session_id: sessionId || null }),
    });
    if (!r.ok) return { ok: false, message: `couldn't cancel that (${r.status}).` };
    return { ok: true, message: "cancelled." };
  }

  if (name === "get_todays_schedule") {
    const r = await fetch(`${API}/schedule/public/today`);
    if (!r.ok) return { ok: false, message: `couldn't reach the schedule (${r.status}).` };
    const items = await r.json();
    if (!items.length) return { ok: true, message: "nothing is listed on today's schedule yet." };
    const lines = items.map((i) => `${i.time_label ? `${i.time_label}: ` : ""}${i.title}`);
    return { ok: true, message: `today: ${lines.join("; ")}.` };
  }

  if (name === "get_menu") {
    const qs = new URLSearchParams();
    if (args.meal_period) qs.set("meal_period", args.meal_period);
    if (args.date) qs.set("date", args.date);
    const r = await fetch(`${API}/menu/public/today?${qs.toString()}`);
    if (!r.ok) return { ok: false, message: `couldn't reach the menu (${r.status}).` };
    const items = await r.json();
    if (!items.length) {
      return { ok: true, message: `I don't have today's ${args.meal_period || "menu"} yet - let me check and get back to you.` };
    }
    const lines = items.map((i) => `${i.meal_period}: ${i.item_name}${i.availability ? ` (${i.availability})` : ""}`);
    return { ok: true, message: lines.join("; ") + "." };
  }

  return undefined;
}
