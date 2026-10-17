/**
 * Local, deterministic "end the call" intent (RQ-055, owner P0 da-5fa8c9ef00).
 *
 * Room 214 session rt_t07bct8g, 2026-10-09: the owner said "end the call" /
 * "goodbye" a dozen times. The model heard it every time and called end_call
 * every time, but the speech-to-text (language auto-detect) wrote the short
 * English phrases as Lithuanian, Arabic, Korean, Japanese, Hindi ..., so the
 * transcript-grounding guard refused each call and Aria asked "are you sure?"
 * until one phrase ("Go away.") happened to transcribe correctly.
 *
 * Two independent ways out, neither needs the model to choose a tool:
 *  1. classifyEndIntent(): a clear spoken ending in the transcript ends the call.
 *  2. createEndCorroboration(): the model itself asked to end the call twice in
 *     a row within 90 s on usable (non-echo) turns - the audio-native model
 *     heard something the transcript lost. Second attempt is granted.
 * Both are conservative about quotes, questions, negation and long sentences.
 */
const FILLER = /\b(aria|hey|listen|okay|ok|yes|yeah|yep|no|nope|nah|please|now|right now|just|really|for now|for today|thanks|thank you|then|so|well|alright|all right|i(?:'|’)?m telling you|i said|michael|go ahead and|you can)\b/gi;
const CORE = [
  /^end (the |this |our |that )?(call|conversation|chat)$/,
  /^end it$/, /^hang up( the phone)?$/, /^stop (talking|the call|listening)$/,
  /^good\s?bye( now)?$/, /^bye( bye)?$/, /^good\s?night$/, /^go away$/, /^leave me alone$/,
  /^adi[oó]s$/, /^hasta luego$/, /^chao$/, /^buenas noches$/,
  /^that(?:'|’)?s all$/, /^that(?:'|’)?ll be all$/, /^that will be all$/, /^that is all$/,
  /^we(?:'|’)?re done$/, /^we are done$/, /^i(?:'|’)?m done$/, /^i am done$/, /^i(?:'|’)?m done here$/,
  /^(shut|turn) yourself off$/,   // NOT "turn it off" / "stop": those mean a device or a barge-in, never the call
];
// Farewell lead-ins: a clear ending on their own, and allowed before an ending
// in the same sentence ("I'll talk to you later, goodbye." - Room 214,
// 2026-10-16: one comma made it a five-word sentence, nothing matched, and
// Aria answered "Okay, let me wrap this up..." instead of hanging up).
const LEADS = [
  /^(i(?:'|’)?ll )?talk to you (later|soon|tomorrow)$/, /^(i(?:'|’)?ll )?see you (later|soon|tomorrow)$/,
  /^have a (good|nice) (night|day|evening)$/, /^take care$/, /^bye for now$/,
];
const NEGATED_OR_QUOTED = /(["“”«»]|\b(don(?:'|’)?t|do not|didn(?:'|’)?t|won(?:'|’)?t|not|never|no one|nobody|when i say|if i say|i (?:might|will|would) say|said|says|saying|the (?:phrase|words?|command)|example|means?|like|such as|instead|keep (?:talking|going)|stay|wait)\b)/i;
const QUESTION = /\?|^\s*(can|could|would|will|do|does|did|how|what|why|when|where|who|is|are|should|if)\b/i;

const normal = (s) => s.replace(/[.!,;:]+/g, " ").replace(FILLER, " ").replace(/\s+/g, " ").trim().toLowerCase();

const isEnding = (c) => c.split(" ").length <= 6 && [...CORE, ...LEADS].some((re) => re.test(c));
/** "talk to you later, goodbye" / "okay thanks, bye": every comma clause is an ending or filler, the last a real ending. */
function clausesEnd(sentence) {
  const clauses = sentence.split(/[,;]+/).map(normal).filter(Boolean);
  return clauses.length > 1 && clauses.every(isEnding) && CORE.some((re) => re.test(clauses[clauses.length - 1]));
}

/** "explicit" when some sentence of the utterance is, after filler words, only an ending phrase. */
export function classifyEndIntent(text) {
  const raw = (text || "").trim();
  if (!raw || raw.length > 160) return "none";
  const sentences = raw.split(/(?<=[.!?])\s+/).filter(Boolean);
  let explicit = false;
  for (const s of sentences) {
    if (NEGATED_OR_QUOTED.test(s) || QUESTION.test(s)) return "none";
    const n = normal(s);
    if (n && n.split(" ").length <= 6 && [...CORE, ...LEADS].some((re) => re.test(n))) explicit = true;
    else if (clausesEnd(s)) explicit = true;
  }
  return explicit ? "explicit" : "none";
}

/** Turn classes that may carry an end command. echo_like = Aria's own words coming back. */
export function turnMayEnd(reason) {
  return reason !== "echo_like" && reason !== "repeated_tiny_fragments";
}

const WINDOW_MS = 90000;
/** Counts the model's own end_call attempts that the transcript guard refused. */
export function createEndCorroboration(now = Date.now) {
  let attempts = [];
  return {
    /** Returns true when this refused attempt should be granted anyway. */
    onRefusedAttempt(reason) {
      if (!turnMayEnd(reason)) return false;
      const t = now();
      attempts = attempts.filter((a) => t - a < WINDOW_MS);
      attempts.push(t);
      return attempts.length >= 2;
    },
    reset() { attempts = []; },
  };
}

/**
 * True when a transcript is clearly NOT something said in this home (English
 * or Spanish practice): it contains letters but none in the Latin script
 * (Arabic, Korean, Japanese, Hindi ... - the 2026-10-09 mis-detections), or it
 * is empty. Used only to decide whether the model's end_call can be trusted
 * on its first attempt; the transcript text is never acted on itself.
 */
export function transcriptIsOutOfScript(text) {
  const t = (text || "").trim();
  if (!t) return true;
  return /\p{L}/u.test(t) && !/\p{Script=Latin}/u.test(t);
}
