/**
 * RQ-052: how far ahead of audible playback does the streamed assistant transcript run?
 * The claim interrupter can only cut speech the transcript has already revealed, so the real
 * delta-ahead-of-playback lead decides how much of a false sentence is heard before it is
 * caught. Observability only: logs one `transcript_delta_lead` event per response.
 *   lead_ms          audio_started_at - first_delta_at   (> 0: text ran ahead of audio)
 *   chars_before_audio  transcript characters already streamed when playback began
 * A response whose audio never starts logs lead_ms: null (nothing was ever heard).
 */
export function createDeltaLead(log, now = () => Date.now()) {
  const byResponse = new Map();   // response_id -> { first, chars, logged }
  let latest = null;              // most recent response id that streamed text
  const entry = (id) => { if (!byResponse.has(id)) byResponse.set(id, { first: null, chars: 0, logged: false }); return byResponse.get(id); };
  const emit = (id, e, audioAt) => {
    if (e.logged) return;
    e.logged = true;
    log("transcript_delta_lead", { meta: {
      response_id: id,
      lead_ms: audioAt != null && e.first != null ? audioAt - e.first : null,
      chars_before_audio: audioAt != null ? e.chars : null,
      total_chars_at_report: e.chars,
    } });
  };
  return {
    onDelta(msg) {
      const id = msg?.response_id || "unknown";
      const e = entry(id);
      if (e.first == null) e.first = now();
      if (!e.logged) e.chars += (msg?.delta || "").length;
      latest = id;
    },
    onAudioStarted(msg) {
      const id = msg?.response_id || latest;
      if (!id || !byResponse.has(id)) return;
      emit(id, byResponse.get(id), now());
    },
    onResponseDone(response) {
      const id = response?.id;
      if (id && byResponse.has(id)) { emit(id, byResponse.get(id), null); byResponse.delete(id); }
      if (byResponse.size > 20) byResponse.delete(byResponse.keys().next().value);
    },
  };
}
