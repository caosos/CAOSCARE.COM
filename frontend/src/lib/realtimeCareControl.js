/**
 * Level 1 resident-assistance event (2026-09-06 directive) - the optional
 * live staff line. Same structural-grounding technique already used for
 * RESTING_PHRASES/ENDING_PHRASES in realtimeDeviceTools.js: the resident's
 * OWN transcript is matched against real phrases, never the model's own
 * unverified interpretation of intent.
 *
 * "Both" halves of the live-line decision live on the BACKEND
 * (routes/alert_lifecycle_events.py's /live-line/ring: an urgent card on
 * the already-open staff dashboard, plus a best-effort Twilio call). This
 * module only decides WHEN to ring - the routing question the directive
 * specifies, asked once, resolved by what the resident actually says.
 */
import { API } from "./api";
import { executeOperationsTool } from "./realtimeOperationsTools";

const IMMEDIATE_PHRASES = /\b(now|right now|hurt|fell|fallen|can'?t breathe|help me|emergency|please hurry|need (someone|help) now)\b/i;
const COMPANIONABLE_PHRASES = /\b(lonely|dinner|company|can wait|no rush|not urgent|just (want(ed)?|wanted) to talk|talk to you)\b/i;

// Has the routing question already been asked for this event? Module-scope
// (not per-hook state) is safe here: a kiosk is one long-lived page per
// room, one event's request_live_staff calls happen sequentially, and a
// genuinely new event gets a new alert_id this Set has never seen.
const askedAlertIds = new Set();

// True only when the backend accepted the ring. A failed or unreachable ring
// must never be reported to the resident as "getting someone".
async function ringLiveLine(alertId) {
  if (!alertId) return false;
  try {
    const r = await fetch(`${API}/alerts/${encodeURIComponent(alertId)}/live-line/ring`, { method: "POST" });
    return !!r && r.ok !== false;
  } catch {
    return false;
  }
}

// RQ-031 (D1): when the live line cannot be used, the resident's ask must
// not be dropped. File the same ask as an ordinary nursing request and say
// ONLY what the system did - never that anyone is aware, coming, or on the
// way, because nothing established that.
const NEEDS_NOW = /\b(now|right now|hurt|fell|fallen|can'?t breathe|help me|emergency|please hurry|need (a nurse|someone|help))\b/i;
const NO_ARRIVAL = "I can't tell you that anyone has seen it or is on the way yet.";

async function fileInsteadOfLiveLine(ctx, heard) {
  const result = await executeOperationsTool({
    name: "request_staff_help",
    args: {
      category: "nursing",
      summary: heard || "Resident asked for a nurse or staff member.",
      priority: NEEDS_NOW.test(heard) ? "high" : "normal",
    },
    ctx: {
      room: ctx?.room, residentId: ctx?.resident_id, sessionId: ctx?.session_id,
      turnSuspect: ctx?.turn_suspect, turnSuspectReason: ctx?.turn_suspect_reason,
    },
  });
  if (result?.ok) {
    return {
      ok: true, filed: true, rang: false, task_id: result.task_id,
      message: `I couldn't reach staff on the live line, so I sent a nursing request instead. ${NO_ARRIVAL}`,
    };
  }
  return {
    ok: false, filed: false, rang: false,
    message: `${result?.message || "I couldn't send that request."} Nothing was sent to staff. Please use the call button. ${NO_ARRIVAL}`,
  };
}

// Called from realtimeMessageHandler.js when the routing-question silence
// timer expires with no resolving answer - directive: "if silence/
// unintelligible after the live-line question -> treat as now -> ring."
export async function ringLiveLineOnSilence(alertId) {
  await ringLiveLine(alertId);
}

export async function executeCareTool({ name, args, ctx }) {
  if (name !== "request_live_staff") return undefined;
  const alertId = ctx?.alert_id;
  const heard = (ctx?.last_user_text || "").trim();
  if (!alertId) return fileInsteadOfLiveLine(ctx, heard);

  if (IMMEDIATE_PHRASES.test(heard)) {
    if (!(await ringLiveLine(alertId))) return fileInsteadOfLiveLine(ctx, heard);
    return { ok: true, message: "Okay, I'm getting someone for you right now.", rang: true };
  }
  if (COMPANIONABLE_PHRASES.test(heard)) {
    await fetch(`${API}/alerts/${encodeURIComponent(alertId)}/aria-event`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event: "requested_staff", utterance: heard || null }),
    }).catch(() => {});
    return { ok: true, message: "Okay, I'll stay right here with you until they arrive.", rang: false };
  }

  // Ambiguous ("get me a nurse" with no urgency cue either way) OR this is
  // the resident's answer to a question already asked once and it still
  // isn't clear - the directive doesn't call for a second question, so a
  // repeat unclear turn is treated the same as silence would be: err
  // toward ringing rather than asking again.
  if (askedAlertIds.has(alertId)) {
    if (!(await ringLiveLine(alertId))) return fileInsteadOfLiveLine(ctx, heard);
    return { ok: true, message: "Okay, I'm getting someone for you right now.", rang: true };
  }
  askedAlertIds.add(alertId);
  await fetch(`${API}/alerts/${encodeURIComponent(alertId)}/aria-event`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event: "requested_staff", utterance: heard || null }),
  }).catch(() => {});
  return {
    ok: true, rang: false, awaiting_answer: true, ring_timeout_sec: ctx?.live_line_ring_timeout_sec,
    message: "Do you want someone in the room right now, or can you talk to me until they get here?",
  };
}
