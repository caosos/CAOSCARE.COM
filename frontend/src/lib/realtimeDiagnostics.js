import { API } from "./api";

// Confidence estimate (0-1) from OpenAI's per-token transcription logprobs
// (requested via session.update's "include": ["item.input_audio_transcription.logprobs"]).
// exp(mean logprob) is the standard way to turn log-probabilities back into
// a probability-like score. A real signal for "was this actually said",
// not a proxy like audio-overlap timing - the threshold below is a
// starting point, not calibrated against this deployment's real data yet.
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

const count = (value) => Number.isInteger(value) && value >= 0 ? value : 0;

// Keep only provider billing counters. Never persist the full response:
// it may contain generated text, audio/tool payloads, or future secrets.
export function sanitizeRealtimeUsage(usage) {
  if (!usage || typeof usage !== "object") return null;
  const input = usage.input_token_details || {};
  const cached = input.cached_tokens_details || {};
  const output = usage.output_token_details || {};
  return {
    total_tokens: count(usage.total_tokens),
    input_tokens: count(usage.input_tokens),
    output_tokens: count(usage.output_tokens),
    input_token_details: {
      text_tokens: count(input.text_tokens), audio_tokens: count(input.audio_tokens),
      cached_tokens: count(input.cached_tokens),
      cached_tokens_details: { text_tokens: count(cached.text_tokens), audio_tokens: count(cached.audio_tokens) },
    },
    output_token_details: { text_tokens: count(output.text_tokens), audio_tokens: count(output.audio_tokens) },
  };
}

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
