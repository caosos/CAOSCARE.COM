/**
 * Is this speech segment the tail of a sentence the resident is still saying?
 *
 * Room 214 rt_d3ahe1bf, 2026-10-21 19:33 CDT: "I thought that you were running simulations
 * right now that added menus to your ... information, that's all." Server VAD split it at
 * short pauses into "...menus to your" / "Information" / "That's all." The last piece alone
 * read as an explicit ending and the call hung up; Michael had not said goodbye.
 *
 * A segment continues the previous one when it started within CONTINUES_MS of the previous
 * segment's end and Aria's audio did not play in between. Only soft endings ("that's all",
 * "I'm done") are held back for it (endIntent.isSoftEnding); "goodbye", "bye", "goodnight",
 * "hang up" always end the call.
 */
export const CONTINUES_MS = 1200;

export function createSentenceTail({ now = () => Date.now() } = {}) {
  let lastStop = null, ariaSpoke = false;
  const seg = new Map();   // item_id -> { gap, ariaBetween }
  return {
    onSpeechStarted(itemId) {
      if (itemId) seg.set(itemId, { gap: lastStop === null ? null : now() - lastStop, ariaBetween: ariaSpoke });
      if (seg.size > 50) seg.delete(seg.keys().next().value);
    },
    onSpeechStopped() { lastStop = now(); ariaSpoke = false; },
    onAriaAudio() { ariaSpoke = true; },
    continues(itemId) {
      const s = seg.get(itemId);
      return Boolean(s) && s.gap !== null && s.gap < CONTINUES_MS && !s.ariaBetween;
    },
  };
}
