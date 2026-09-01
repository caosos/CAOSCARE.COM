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
const WAIT_MAX_MS = 900; // observed real lag was 137-184ms; generous ceiling, not a typical wait.

export function createTurnGroundingTracker() {
  let lastKnownUserTurn = { suspect: false, reason: "no_overlap", text: "" };
  let transcriptPending = false;
  return {
    onSpeechStopped() { transcriptPending = true; },
    onTranscriptionCompleted(cls, userText) {
      lastKnownUserTurn = { ...cls, text: userText };
      transcriptPending = false;
    },
    async waitForGroundedTurn() {
      const start = Date.now();
      while (transcriptPending && Date.now() - start < WAIT_MAX_MS) {
        await new Promise((r) => setTimeout(r, 50));
      }
      return lastKnownUserTurn;
    },
  };
}
