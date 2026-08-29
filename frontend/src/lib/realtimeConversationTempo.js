/**
 * Adaptive turn-taking for Realtime voice.
 *
 * OpenAI server_vad still detects/chunks speech, but automatic responses stay
 * off. This controller decides when to send response.create so a short pause
 * is not automatically treated as "I'm done talking." It learns from one
 * concrete signal: if the person resumes before Aria answers, give them a
 * little more room next time. If they consistently yield the floor, tighten
 * the delay gradually.
 */
import { logRealtimeEvent } from "./realtimeDiagnostics";

const PROFILES = {
  operator: { initial: 250, min: 150, max: 1200, resumeStep: 150, settleStep: 25 },
  resident: { initial: 450, min: 300, max: 1600, resumeStep: 150, settleStep: 20 },
};
const FALLBACK_ITEM = "__current_speech_turn__";

export const CONVERSATION_RHYTHM_INSTRUCTIONS = `## Conversation rhythm
Match the person's conversational tempo instead of imposing your own. Let them finish. A pause, filler word, restart, half-sentence, or quick change of direction is not automatically the end of their thought. If they speak quickly, keep your replies tighter and move with them. If they slow down or search for words, leave more room. If they interrupt you, yield immediately and follow the new thread. Do not answer an obviously unfinished fragment, and do not fill every silence.`;

export function withConversationRhythm(instructions = "") {
  return `${instructions}\n\n${CONVERSATION_RHYTHM_INSTRUCTIONS}`;
}

export function createConversationTempoController({ send, sessionIdRef, ctxRef }) {
  const profile = ctxRef.current?.owner_user_id ? PROFILES.operator : PROFILES.resident;
  const mode = ctxRef.current?.owner_user_id ? "operator" : "resident";
  let graceMs = profile.initial;
  let timer = null;
  let pendingItemId = null;
  let latestItemId = null;
  const overlapItems = new Set();
  const keyFor = (itemId) => itemId || FALLBACK_ITEM;

  const log = (event, meta = {}) => {
    logRealtimeEvent(sessionIdRef.current, event, {
      meta: { mode, grace_ms: graceMs, ...meta },
    });
  };

  const clearPending = () => {
    if (!timer) return false;
    clearTimeout(timer);
    timer = null;
    pendingItemId = null;
    return true;
  };

  const scheduleResponse = (itemId) => {
    const itemKey = keyFor(itemId);
    if (latestItemId && itemKey !== latestItemId) return;
    clearPending();
    pendingItemId = itemKey;
    timer = setTimeout(() => {
      timer = null;
      pendingItemId = null;
      send({ type: "response.create" });
      log("tempo_response_create", { item_id: itemId || null });
      graceMs = Math.max(profile.min, graceMs - profile.settleStep);
    }, graceMs);
    log("tempo_response_scheduled", { item_id: itemId || null });
  };

  const speechStarted = ({ itemId = null } = {}) => {
    latestItemId = keyFor(itemId);
    if (!clearPending()) return;
    graceMs = Math.min(profile.max, graceMs + profile.resumeStep);
    log("tempo_user_resumed", { item_id: itemId || null });
  };

  const speechStopped = ({ itemId = null, overlapped = false } = {}) => {
    const itemKey = keyFor(itemId);
    latestItemId = itemKey;
    if (overlapped) {
      overlapItems.add(itemKey);
      log("tempo_waiting_for_overlap_classification", { item_id: itemId || null });
      return;
    }
    scheduleResponse(itemId);
  };

  const classified = ({ itemId = null, suspect = false, reason = "unknown" } = {}) => {
    const itemKey = keyFor(itemId);
    if (suspect) {
      if (pendingItemId === itemKey) clearPending();
      overlapItems.delete(itemKey);
      log("tempo_suspect_turn_suppressed", { item_id: itemId || null, reason });
      return;
    }
    if (!overlapItems.has(itemKey)) return;
    overlapItems.delete(itemKey);
    scheduleResponse(itemId);
  };

  const responseCreated = () => {
    // A response may be created by a greeting or tool path. Never leave a
    // delayed floor-taking response queued behind an already-starting one.
    clearPending();
  };

  return {
    speechStarted,
    speechStopped,
    classified,
    responseCreated,
    cancel: clearPending,
  };
}
