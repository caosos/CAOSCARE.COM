import { API } from "./api";

// Confidence estimate (0-1) from OpenAI's per-token transcription logprobs
// (requested via session.update's "include": ["item.input_audio_transcription.logprobs"]).
// exp(mean logprob) is the standard way to turn log-probabilities back into
// a probability-like score. A real signal for "was this actually said",
// not a proxy like audio-overlap timing - the threshold below is a
// starting point, not calibrated against this deployment's real data yet.
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

export function transcriptionConfidence(logprobs) {
  if (!Array.isArray(logprobs) || logprobs.length === 0) return null;
  const mean = logprobs.reduce((sum, l) => sum + (l.logprob ?? 0), 0) / logprobs.length;
  return Math.exp(mean);
}

// Fire-and-forget Realtime event logger - so a live-test defect (phantom
// transcripts, double greetings, echo) can be reconstructed from real event
// timing afterward instead of guessed at. Never blocks the call; a failed
// log is silently dropped. Never pass raw audio or secrets in meta/text.
export function logRealtimeEvent(sessionId, eventType, { assistantSpeaking, text, responseId, meta } = {}) {
  try {
    fetch(`${API}/realtime-diagnostics/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        event_type: eventType,
        assistant_speaking: assistantSpeaking ?? null,
        text: text ?? null,
        response_id: responseId ?? null,
        meta: meta ?? null,
      }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // never let a diagnostics failure touch the live call
  }
}
