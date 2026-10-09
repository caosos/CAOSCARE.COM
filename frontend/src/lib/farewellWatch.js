/**
 * RQ-041 observability: Aria said a farewell but never called end_call
 * (Room 214 session rt_zu1x1e37: "Goodnight, Michael..." with the session
 * left open). Counted, not acted on - we never auto-hang-up.
 */
export const FAREWELL = /\b(good\s?night|goodbye|good-bye|take care|talk to you (?:soon|later))\b/i;
const END_TOOLS = new Set(["end_call", "end_conversation"]);

export function createFarewellWatch(log) {
  let farewellText = null;
  return {
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
      log("farewell_without_end_call", { text, responseId: response?.id });
      return true;
    },
  };
}
