/**
 * AriaVoice — Michael's own conversational assistant (Terminal 5 Phase C).
 *
 * Deliberately minimal: prove full-duplex audio + conversation works before
 * building any decorative UI. Reuses useRealtimeVoice pointed at
 * /realtime/aria-session (Aria's own persona/instructions) instead of the
 * resident-facing /realtime/session. No tools wired yet — pure conversation.
 */
import React, { useEffect, useRef } from "react";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { useRealtimeVoice } from "../lib/useRealtimeVoice";

export default function AriaVoice() {
  const { user } = useAuth();
  const { status, error, transcript, start, stop, audioElRef } = useRealtimeVoice({
    voice: "sage",
    sessionEndpoint: "/realtime/aria-session",
    sessionPayload: { voice: "sage", owner_user_id: user?.user_id || null },
  });
  const localAudioElRef = useRef(null);

  useEffect(() => {
    audioElRef.current = localAudioElRef.current;
  }, [audioElRef]);

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
        {transcript.map((t, i) => (
          <p key={i} className={t.role === "assistant" ? "text-caos-forest" : "text-caos-mute"}>
            <strong>{t.role === "assistant" ? "Aria: " : "You: "}</strong>{t.text}
          </p>
        ))}
      </div>

      <audio ref={localAudioElRef} autoPlay />
    </div>
  );
}
