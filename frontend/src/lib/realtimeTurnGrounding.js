/**
 * Tracks the last COMPLETED user turn for tool-call grounding, separately
 * from turnSuspectRef's brief boolean-overlap-flag role in
 * realtimeMessageHandler.js, and gives tool-call dispatch a bounded wait
 * for a same-turn transcription race to resolve.
 *
 * 2026-08-30 (real live defect, confirmed live, room 401): the model can
 * call a tool from raw audio before the SEPARATE transcription pipeline
 * for that same utterance finishes (observed live: function_call_
 * arguments.done landing 137-184ms before conversation.item.input_audio_
 * transcription.completed for the very turn that triggered it). Reading
 * turnSuspectRef mid-race meant handleFunctionCall saw its brief boolean
 * shape (set on speech_started), not the {suspect,reason,text} object
 * (set on transcription-completed) - `.text` came back undefined - and
 * the backend's ENDING_PHRASES/RESTING_PHRASES grounding guards rejected
 * clearly genuine "go away"/"end the call" requests as ungrounded,
 * repeatedly, on the exact same turn every time.
 */
const TYPED_HOLD_MS = 6000; // a typed request stays the grounding turn against a stray 1-2 word mic fragment this soon after
const WAIT_MAX_MS = 1500; // Room 214 can deliver the model's tool call before VAD stop/transcription; still bounded.

export function createTurnGroundingTracker() {
  let lastKnownUserTurn = { suspect: false, reason: "no_overlap", text: "" };
  let transcriptPending = false;
  let pendingOverlap = false;
  let typedAt = 0;
  return {
    // A model tool call can arrive before speech_stopped. Mark the turn pending
    // at speech_started so it cannot be grounded against the previous turn.
    onSpeechStarted(overlapped = false) { transcriptPending = true; pendingOverlap = overlapped; },
    onSpeechStopped() { transcriptPending = true; },
    onTranscriptionCompleted(cls, userText) {
      transcriptPending = false;
      pendingOverlap = false;
      if (cls?.reason === "typed") typedAt = Date.now();
      // 2026-10-10 (demo kiosk, live): "Turn the volume up a little." typed, then a 1 s mic fragment ("Pekmez.") landed
      // before the tool call and replaced it as the grounding text, so the volume command was refused as ungrounded.
      // A typed turn is not replaced by a 1-2 word mic fragment within TYPED_HOLD_MS; anything longer still replaces it.
      const words = String(userText || "").trim().split(/\s+/).filter(Boolean).length;
      if (cls?.reason !== "typed" && typedAt && Date.now() - typedAt < TYPED_HOLD_MS && words <= 2) return;
      lastKnownUserTurn = { ...cls, text: userText };
    },
    async waitForGroundedTurn() {
      const start = Date.now();
      while (transcriptPending && Date.now() - start < WAIT_MAX_MS) {
        await new Promise((r) => setTimeout(r, 50));
      }
      // Never ground a new tool call against the previous utterance. If the
      // current transcript is still missing, return an honest empty current
      // turn. A non-overlapping audio-native end_call can then use the
      // existing out-of-script corroboration path; every state-changing room
      // tool still sees no resident words and refuses safely.
      if (transcriptPending) return {
        suspect: pendingOverlap,
        reason: pendingOverlap ? "overlap_pending" : "no_overlap_pending",
        text: "",
        pending: true,
      };
      return lastKnownUserTurn;
    },
  };
}
