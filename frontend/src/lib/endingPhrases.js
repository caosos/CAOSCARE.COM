/**
 * Grounding for end_call / end_conversation (RQ-038).
 *
 * The model may only hang up when the resident's own last words say so.
 * 2026-10-08 (Room 214, four live sessions): genuine endings such as
 * "That will be all for now, Aria." and "That'll be it for now, thank you."
 * were refused, so the model re-asked up to five times in one call. The
 * phrase list is widened here; unrelated utterances ("It's gonna find me.",
 * "No, I can't.", "That's beautiful.") still refuse.
 *
 * If the guard refuses and the resident's NEXT turn is a short "yes", the
 * end is grounded; a bare "no" clears the question. After two refusals in a
 * row the guard stops re-prompting (the model is told not to ask again).
 * State is per session id and lives only in this module.
 */
export const ENDING_PHRASES = new RegExp(
  "\\b(" + [
    "end (the |this |our )?(call|conversation|chat)",
    "end it",
    "hang up",
    "stop (talking|the call)",
    "good\\s*bye",
    "bye( bye)?",
    "good\\s*night",
    "see you",
    "talk to you (later|soon|tomorrow)",
    "that(?:'|’)?s all( for now)?",
    "that(?:'|’)?ll be all( for now)?",
    "that will be all( for now)?",
    "that is all( for now)?",
    "that(?:'|’)?ll be it( for now)?",
    "that will be it( for now)?",
    "that(?:'|’)?s it( for now)?",
    "we(?:'|’)?re done",
    "we are done",
    "i(?:'|’)?m done",
    "i am done",
    "don(?:'|’)?t need you",
    "go away",
  ].join("|") + ")\\b",
  "i",
);

const AFFIRMATIVE = /^\s*(yes|yeah|yep|yup|please|sure|go ahead|do it|that(?:'|’)?s right|that is right|correct|okay|ok)\b[\s,.!a-z']{0,20}$/i;
const NEGATIVE = /^\s*(no|nope|nah|not yet|don(?:'|’)?t)\b/i;

export const MAX_END_REFUSALS = 2;

const states = new Map(); // session id -> { refusals, pendingText }
const stateFor = (sid) => {
  const key = sid || "_";
  if (!states.has(key)) states.set(key, { refusals: 0, pendingText: null });
  return states.get(key);
};
export function resetEndingState(sid) {
  if (sid === undefined) states.clear(); else states.delete(sid || "_");
}

const ASK = "Sorry, I want to make sure — did you want to end our conversation?";
const FINAL = "The resident has not asked to end the conversation, and you have already checked twice. Do NOT ask again. Carry on helping; they can simply say goodbye when they are ready.";

/** Returns { ok:true } when the resident's words ground an end, else { ok:false, message }. */
export function checkEnding(sid, heard) {
  const st = stateFor(sid);
  const text = (heard || "").trim();
  if (text && ENDING_PHRASES.test(text)) {
    st.refusals = 0; st.pendingText = null;
    return { ok: true };
  }
  if (st.pendingText && text && text !== st.pendingText) {
    st.pendingText = null;
    if (AFFIRMATIVE.test(text)) { st.refusals = 0; return { ok: true }; }
    if (NEGATIVE.test(text)) { st.refusals = 0; return { ok: false, message: "Okay, we'll keep going." }; }
  }
  st.refusals += 1;
  if (st.refusals > MAX_END_REFUSALS) return { ok: false, final: true, message: FINAL };
  st.pendingText = text || null;
  return { ok: false, message: ASK };
}
