/**
 * RQ-041 observability: Aria said a farewell but never called end_call
 * (Room 214 session rt_zu1x1e37: "Goodnight, Michael..." with the session
 * left open). Counted, not acted on - we never auto-hang-up.
 */
export const FAREWELL = /\b(good\s?night|goodbye|good-bye|take care|talk to you (?:soon|later))\b/i;
const END_TOOLS = new Set(["end_call", "end_conversation"]);

// The goodbye is spoken in the response AFTER the end_call tool-call response
// (audit rt_dc5h0fi1: end_call 03:36:31.468, goodbye 03:36:32.626), so an
// ok end_call seen shortly before also satisfies the watch.
const END_CALL_GRACE_MS = 15000;

export function createFarewellWatch(log, now = Date.now) {
  let farewellText = null;
  let endCallOkAt = null;
  return {
    /** The handler calls this when end_call/end_conversation returned ok:true. */
    noteEndCallOk() { endCallOkAt = now(); },
    onAssistantTranscript(text) {
      if (text && FAREWELL.test(text)) farewellText = text;
    },
    /** Call on response.done with the response object. */
    onResponseDone(response) {
      const text = farewellText;
      farewellText = null;
      if (!text) return false;
      const called = (response?.output || []).some((o) => o?.type === "function_call" && END_TOOLS.has(o.name));
      if (called) return false;
      if (endCallOkAt !== null && now() - endCallOkAt <= END_CALL_GRACE_MS) return false;
      log("farewell_without_end_call", { text, responseId: response?.id });
      return true;
    },
  };
}
