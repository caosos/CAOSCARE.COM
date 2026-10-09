/**
 * Shapes a POST /research response for the model (RQ-046).
 * Room 214 rt_dc5h0fi1: with no live provider the endpoint answered from a
 * plain model and Aria told the resident "I did check the internet". Only
 * a live result (live === true, openai_web_search source, citations) may read as a
 * lookup; anything else is labelled as general knowledge. A missing `live`
 * field (older backend) counts as not live.
 */
export const NOT_LIVE_PREFIX =
  "NOT A LIVE LOOKUP: I have no internet access right now. This is general knowledge only and may be out of date or wrong: ";

export function shapeResearchResult(j) {
  const answer = j?.answer || "I didn't find anything useful on that.";
  const citations = Array.isArray(j?.citations) ? j.citations : [];
  const live = j?.live === true && j?.source === "openai_web_search" && citations.length > 0;
  if (!live) return { ok: true, live: false, message: NOT_LIVE_PREFIX + answer };
  return { ok: true, live: true, message: answer, source: j.source, citations, citations_detail: Array.isArray(j.citations_detail) ? j.citations_detail : [] };
}
