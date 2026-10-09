/**
 * RQ-046 observability: Aria claimed something no tool result supports
 * (Room 214 rt_dc5h0fi1: "I'll let the team know" with no request filed,
 * weather with no get_weather call, "I checked the internet" with no live
 * lookup). Logged only - never blocks speech, never acts. Same wiring shape
 * as farewellWatch.js.
 */
export const ACTION_CLAIM = new RegExp(
  [
    "\\bI(?:'ll| will)\\s+(?:let|tell|notify|inform|pass|send|alert)\\b[^.!?]*\\b(?:team|staff|nurse|someone|them|along)\\b",
    "\\bI(?:'ve| have)\\s+(?:just\\s+)?(?:sent|notified|told|asked|informed|alerted|changed|turned|set|booked|scheduled)\\b",
    "\\bI\\s+(?:sent|notified|told|asked|informed|alerted|changed|turned|set|booked|scheduled)\\b",
    "\\b(?:the\\s+)?(?:team|staff|nurse)\\s+(?:has|have|was|were)\\s+(?:been\\s+)?(?:notified|told|alerted|informed)\\b",
  ].join("|"),
  "i",
);
export const WEATHER_CLAIM = /\b(weather|forecast|temperature outside|cool and clear|sunny|raining|rainy)\b/i;
export const LOOKUP_CLAIM = /\b(I looked (?:it|that|this) up|I (?:did )?check(?:ed)? the internet|I searched)\b/i;

const ACTION_TOOL = /^(request_|toggle_|set_|adjust_|update_|cancel_|change_|call_for_help|end_call|end_conversation|confirm_|transfer_|mark_)/;

export function createClaimGuard(log) {
  let okActions = new Set();
  let okWeather = false;
  let okLiveLookup = false;
  let pendingText = null;
  return {
    /** New resident turn: results from earlier turns no longer back a claim. */
    onUserTurn() { okActions = new Set(); okWeather = false; okLiveLookup = false; },
    onToolResult(name, result) {
      if (!result || result.ok !== true) return;
      if (name === "get_weather") okWeather = true;
      else if (name === "research_topic") { if (result.live === true) okLiveLookup = true; }
      else if (ACTION_TOOL.test(name)) okActions.add(name);
    },
    onAssistantTranscript(text) { if (text) pendingText = (pendingText ? pendingText + " " : "") + text; },
    /** Call on response.done with the response object; returns the event types logged. */
    onResponseDone(response) {
      const text = pendingText;
      pendingText = null;
      if (!text) return [];
      const called = (response?.output || [])
        .filter((o) => o?.type === "function_call").map((o) => o.name);
      const calledAction = called.some((n) => ACTION_TOOL.test(n));
      const calledWeather = called.includes("get_weather");
      const calledResearch = called.includes("research_topic");
      const logged = [];
      if (ACTION_CLAIM.test(text) && okActions.size === 0 && !calledAction) {
        log("unsupported_action_claim", { text }); logged.push("unsupported_action_claim");
      }
      if (WEATHER_CLAIM.test(text) && !okWeather && !calledWeather) {
        log("unsupported_fresh_fact_claim", { text }); logged.push("unsupported_fresh_fact_claim");
      }
      if (LOOKUP_CLAIM.test(text) && !okLiveLookup && !calledResearch) {
        log("unsupported_lookup_claim", { text }); logged.push("unsupported_lookup_claim");
      }
      return logged;
    },
  };
}
