/**
 * RealtimeChatScreen — full-duplex CAOS Care voice surface.
 *
 * Shown when the resident is in a call AND realtime mode is enabled. Replaces
 * the legacy turn-based chat UI with a single living voice panel: the orb
 * pulses while CAOS speaks, the transcript lands beneath it, and the user
 * can chime in any time without breaking the flow.
 */
import React, { useEffect, useRef } from "react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Mic, X, Volume2, AlertCircle } from "lucide-react";
import { useRealtimeVoice } from "../lib/useRealtimeVoice";

export default function RealtimeChatScreen({
  resident,
  kiosk,
  voiceId,
  onEnd,
  onOpenVoicePicker,
  a11yRootClass,
  triggerSource,
}) {
  const { status, error, transcript, resting, start, stop, audioElRef } = useRealtimeVoice({
    voice: voiceId,
    residentId: resident?.resident_id,
    kioskId: kiosk?.kiosk_id,
    room: kiosk?.room || resident?.room,
    onEndCall: onEnd,
    triggerSource,
  });
  // Room already owned by another live session (server-side lease) — this
  // instance never touched the mic. Show it briefly, then return the kiosk
  // to idle so normal polling/triggers resume; there's nothing to tear down.
  useEffect(() => {
    if (status !== "unavailable") return;
    const t = setTimeout(() => onEnd?.(), 2500);
    return () => clearTimeout(t);
  }, [status, onEnd]);
  const localAudioElRef = useRef(null);
  const startedRef = useRef(false);

  // Hand the in-DOM audio element to the hook so playback is reliable
  // across browsers (some refuse to play off-DOM media).
  useEffect(() => {
    audioElRef.current = localAudioElRef.current;
  }, [audioElRef]);

  useEffect(() => {
    if (startedRef.current) return;        // StrictMode guard — only ever start once
    startedRef.current = true;
    start();
    return () => stop("component_unmount");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const orbState =
    resting ? "" :
    status === "speaking" ? "caos-orb-speak" :
    status === "listening" ? "caos-orb-listen" :
    status === "live" ? "caos-orb" : "";

  return (
    <div
      className={`min-h-screen bg-caos-ambient p-6 md:p-10 flex flex-col ${a11yRootClass || ""}`}
      data-testid="kiosk-realtime-screen"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute">
            Full-duplex · OpenAI Realtime
          </p>
          <h2 className="font-display text-3xl md:text-5xl font-light text-caos-forest mt-2">
            Aria is here with you.
          </h2>
          {resident && (
            <p className="text-caos-mute mt-1 text-lg" data-testid="kiosk-realtime-resident">
              Room {resident.room} · {resident.name}
            </p>
          )}
          <div className="mt-3 flex items-center gap-2 text-xs uppercase tracking-widest text-caos-forest font-bold">
            <StatusDot status={status} />
            <span data-testid="kiosk-realtime-status">{labelFor(status)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={onOpenVoicePicker}
            data-testid="kiosk-realtime-voice-btn"
            className="border-2 h-12 rounded-full"
          >
            <Volume2 className="w-4 h-4 mr-2" />
            VOICE: {(voiceId || "shimmer").toUpperCase()}
          </Button>
          <Button
            onClick={() => { stop("ui_end_call_button"); onEnd?.(); }}
            data-testid="kiosk-realtime-end-btn"
            className="bg-caos-terracotta hover:bg-caos-terracotta-dark h-12 rounded-full"
          >
            <X className="w-5 h-5 mr-2" /> End call
          </Button>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center mt-6">
        <div
          className={`w-44 h-44 rounded-full bg-caos-forest ${orbState} mb-8`}
          data-testid="kiosk-realtime-orb"
        />
        <p className="font-display text-2xl text-caos-forest text-center max-w-xl">
          {resting && "Resting. I'll be quiet — speak any time."}
          {!resting && status === "connecting" && "Connecting…"}
          {!resting && status === "live" && "Speak any time — I'm listening."}
          {!resting && status === "listening" && "Listening…"}
          {!resting && status === "speaking" && "I'm speaking. You can chime in any time."}
          {!resting && status === "error" && "Something went wrong. Try again."}
          {!resting && status === "unavailable" && "Aria is already here with someone right now."}
        </p>
        {error && (
          <p className="mt-3 inline-flex items-center gap-2 text-caos-terracotta text-sm">
            <AlertCircle className="w-4 h-4" /> {error}
          </p>
        )}
      </div>

      <Card className="border-caos-line bg-white/70 backdrop-blur p-4 max-h-56 overflow-y-auto mt-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">
          <Mic className="w-3.5 h-3.5" /> Transcript
        </div>
        {transcript.length === 0 && (
          <p className="text-caos-mute italic text-sm">
            Transcript will appear as you speak. Pure-voice mode — no need to read.
          </p>
        )}
        <div className="space-y-1.5">
          {transcript.map((m, i) => (
            <div
              key={i}
              data-testid={`kiosk-realtime-transcript-${i}`}
              className={m.role === "user" ? "text-caos-ink" : "text-caos-forest"}
            >
              <span className="font-bold uppercase text-[10px] tracking-widest mr-2">
                {m.role === "user" ? "You" : "Aria"}
              </span>
              {m.text}
            </div>
          ))}
        </div>
      </Card>

      {/* Hidden audio sink — must be mounted in the DOM for reliable playback. */}
      <audio ref={localAudioElRef} autoPlay playsInline className="hidden" data-testid="kiosk-realtime-audio" />
    </div>
  );
}

function StatusDot({ status }) {
  const color =
    status === "speaking" ? "bg-caos-terracotta" :
    status === "listening" ? "bg-caos-amber" :
    status === "live" ? "bg-caos-forest" :
    status === "error" ? "bg-red-500" :
    status === "unavailable" ? "bg-caos-amber" : "bg-caos-mute";
  return <span className={`inline-block w-2 h-2 rounded-full ${color} ${status === "live" || status === "listening" ? "animate-pulse" : ""}`} />;
}

function labelFor(status) {
  switch (status) {
    case "connecting": return "Connecting";
    case "live": return "Live · idle";
    case "listening": return "Listening";
    case "speaking": return "Speaking";
    case "error": return "Error";
    case "unavailable": return "Already active";
    default: return "—";
  }
}
