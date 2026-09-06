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

const IMMEDIATE_PHRASES = /\b(now|right now|hurt|fell|fallen|can'?t breathe|help me|emergency|please hurry|need (someone|help) now)\b/i;
const COMPANIONABLE_PHRASES = /\b(lonely|dinner|company|can wait|no rush|not urgent|just (want(ed)?|wanted) to talk|talk to you)\b/i;

// Has the routing question already been asked for this event? Module-scope
// (not per-hook state) is safe here: a kiosk is one long-lived page per
// room, one event's request_live_staff calls happen sequentially, and a
// genuinely new event gets a new alert_id this Set has never seen.
const askedAlertIds = new Set();

async function ringLiveLine(alertId) {
  if (!alertId) return;
  await fetch(`${API}/alerts/${encodeURIComponent(alertId)}/live-line/ring`, { method: "POST" }).catch(() => {});
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
  if (!alertId) {
    return { ok: false, message: "I don't have a way to reach staff directly from here right now." };
  }
  const heard = (ctx?.last_user_text || "").trim();

  if (IMMEDIATE_PHRASES.test(heard)) {
    await ringLiveLine(alertId);
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
    await ringLiveLine(alertId);
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
