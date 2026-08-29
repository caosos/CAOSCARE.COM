/**
 * AriaVoice — Michael's own conversational assistant (Terminal 5 Phase C).
 *
 * Deliberately minimal: prove full-duplex audio + conversation works before
 * building any decorative UI. Reuses useRealtimeVoice pointed at
 * /realtime/aria-session (Aria's own persona/instructions) instead of the
 * resident-facing /realtime/session. No tools wired yet — pure conversation.
 */
import React, { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { useRealtimeVoice } from "../lib/useRealtimeVoice";
import { api } from "../lib/api";
import CopyTranscriptButton from "../components/CopyTranscriptButton";

function PastConversations({ ownerId, refreshKey }) {
  const [threads, setThreads] = useState([]);
  const [openThread, setOpenThread] = useState(null); // session_id
  const [turns, setTurns] = useState([]);

  const loadThreads = useCallback(() => {
    if (!ownerId) return;
    api.get(`/aria/conversation-threads/${ownerId}`).then(({ data }) => setThreads(data)).catch(() => {});
  }, [ownerId]);

  useEffect(() => { loadThreads(); }, [loadThreads, refreshKey]);

  const openThreadFn = (sessionId) => {
    if (openThread === sessionId) { setOpenThread(null); return; }
    setOpenThread(sessionId);
    api
      .get(`/aria/conversation-threads/${ownerId}/${sessionId}`)
      .then(({ data }) => setTurns(data))
      .catch(() => setTurns([]));
  };

  if (!threads.length) return null;

  return (
    <div className="w-full max-w-xl mt-10 border-t border-caos-mute/20 pt-6">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-caos-mute mb-3">
        Past conversations
      </p>
      <div className="space-y-2 text-sm">
        {threads.map((t) => (
          <div key={t.session_id}>
            <button
              onClick={() => openThreadFn(t.session_id)}
              className="w-full text-left text-caos-mute hover:text-caos-forest"
            >
              {new Date(t.started_at).toLocaleString()} — {t.turn_count} turns
              {t.preview ? <span className="italic"> · "{t.preview}"</span> : null}
            </button>
            {openThread === t.session_id && (
              <div className="mt-2 mb-3 ml-3 space-y-1 border-l-2 border-caos-mute/20 pl-3">
                <CopyTranscriptButton turns={turns} className="mb-1" />
                {turns.map((turn, i) => (
                  <p key={i} className={turn.role === "assistant" ? "text-caos-forest" : "text-caos-mute"}>
                    <strong>{turn.role === "assistant" ? "Aria: " : "You: "}</strong>{turn.content}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AriaVoice() {
  const { user } = useAuth();
  const { status, error, transcript, start, stop, audioElRef } = useRealtimeVoice({
    voice: "sage",
    sessionEndpoint: "/realtime/aria-session",
    sessionPayload: { voice: "sage", owner_user_id: user?.user_id || null },
  });
  const localAudioElRef = useRef(null);
  const [threadsRefreshKey, setThreadsRefreshKey] = useState(0);
  const prevStatusRef = useRef(status);

  useEffect(() => {
    audioElRef.current = localAudioElRef.current;
  }, [audioElRef]);

  useEffect(() => {
    // Bump the refresh key whenever a session ends (any -> idle) so the
    // thread list picks up the conversation that just happened.
    if (prevStatusRef.current !== "idle" && status === "idle") {
      setThreadsRefreshKey((k) => k + 1);
    }
    prevStatusRef.current = status;
  }, [status]);

  const orbState =
    status === "speaking" ? "caos-orb-speak" :
    status === "listening" ? "caos-orb-listen" :
    status === "live" ? "caos-orb" : "";

  return (
    <div className="min-h-screen bg-caos-ambient p-6 md:p-10 flex flex-col items-center justify-center gap-6">
      <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute">
        Aria · Voice-first proof of concept (Terminal 5 Phase C)
      </p>
      <div className={`w-24 h-24 rounded-full bg-caos-forest ${orbState}`} />
      <p className="text-lg text-caos-forest" data-testid="aria-status">{status}</p>
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="flex gap-3">
        {status === "idle" || status === "error" ? (
          <Button onClick={start} data-testid="aria-start">Start talking with Aria</Button>
        ) : (
          <Button variant="outline" onClick={stop} data-testid="aria-stop">End session</Button>
        )}
      </div>

      <div className="w-full max-w-xl mt-6 space-y-2 text-sm">
        {transcript.length > 0 && (
          <div className="flex justify-end"><CopyTranscriptButton turns={transcript} /></div>
        )}
        {transcript.map((t, i) => (
          <p key={i} className={t.role === "assistant" ? "text-caos-forest" : "text-caos-mute"}>
            <strong>{t.role === "assistant" ? "Aria: " : "You: "}</strong>{t.text}
          </p>
        ))}
      </div>

      <audio ref={localAudioElRef} autoPlay />

      <PastConversations ownerId={user?.user_id} refreshKey={threadsRefreshKey} />
    </div>
  );
}
