import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { AlertCircle, Mic, MicOff, Volume2, Phone, X } from "lucide-react";
import { toast } from "sonner";

// Kiosk is PUBLIC - no login. Selected/identified by kiosk_id in URL.
// /kiosk/:kioskId  (use "demo" to pick an arbitrary kiosk automatically)

export default function Kiosk() {
  const { kioskId } = useParams();
  const nav = useNavigate();

  const [kiosk, setKiosk] = useState(null);
  const [resident, setResident] = useState(null);
  const [callState, setCallState] = useState("idle"); // idle | calling | waiting | chatting
  const [alert, setAlert] = useState(null);
  const [messages, setMessages] = useState([]);
  const [recording, setRecording] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const sessionRef = useRef(`sess_${Math.random().toString(36).slice(2)}`);
  const mediaRef = useRef(null);
  const audioRef = useRef(null);

  // Load kiosk + resident
  useEffect(() => {
    (async () => {
      try {
        let id = kioskId;
        if (id === "demo") {
          const { data: kiosks } = await axios.get(`${API}/kiosks`);
          if (kiosks.length === 0) {
            toast.error("No kiosks provisioned yet.");
            return;
          }
          id = kiosks[0].kiosk_id;
        }
        const { data } = await axios.get(`${API}/residents/public/by-kiosk/${id}`);
        setKiosk(data.kiosk);
        setResident(data.resident);
      } catch {
        toast.error("Could not load kiosk");
      }
    })();
  }, [kioskId]);

  const speak = async (text) => {
    try {
      setSpeaking(true);
      const { data } = await axios.post(`${API}/ai/tts`, { text, voice: "sage" });
      const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
      audioRef.current = audio;
      audio.onended = () => setSpeaking(false);
      audio.onerror = () => setSpeaking(false);
      await audio.play();
    } catch (e) {
      setSpeaking(false);
    }
  };

  const triggerEmergency = async (severity = "emergency") => {
    if (!kiosk) return;
    setCallState("calling");
    try {
      const { data } = await axios.post(`${API}/alerts`, {
        kiosk_id: kiosk.kiosk_id,
        severity,
        message: severity === "emergency" ? "Emergency button pressed" : "Assistance requested",
        triggered_by: "kiosk_button",
      });
      setAlert(data);
      setCallState("waiting");
      const name = resident?.name?.split(" ")[0] || "there";
      const line = severity === "emergency"
        ? `Hello ${name}. Help is on the way. Stay where you are. I am here with you.`
        : `Hello ${name}. I've paged a caregiver. They'll be with you soon. I can stay and chat.`;
      setMessages([{ role: "assistant", content: line }]);
      speak(line);
      setCallState("chatting");
    } catch {
      toast.error("Could not send the call. Please try again.");
      setCallState("idle");
    }
  };

  const cancelCall = async () => {
    if (alert) {
      try {
        // Not a real staff user - just mark as comfort via resolve using a staff? Skip - allow persist.
      } catch {}
    }
    if (audioRef.current) audioRef.current.pause();
    setAlert(null);
    setMessages([]);
    setCallState("idle");
    setSpeaking(false);
  };

  const sendMessage = async (text) => {
    const userMsg = { role: "user", content: text };
    setMessages((m) => [...m, userMsg]);
    setThinking(true);
    try {
      const { data } = await axios.post(`${API}/ai/chat`, {
        session_id: sessionRef.current,
        kiosk_id: kiosk?.kiosk_id,
        resident_id: resident?.resident_id,
        message: text,
      });
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
      speak(data.reply);
      if (data.auto_emergency_detected && alert?.severity !== "emergency") {
        // Escalate silently
        try {
          await axios.post(`${API}/alerts`, {
            kiosk_id: kiosk.kiosk_id,
            severity: "emergency",
            message: "AI triage detected emergency language",
            triggered_by: "ai_triage",
          });
        } catch {}
      }
    } catch {
      toast.error("AI is having a moment. Try again in a sec.");
    } finally {
      setThinking(false);
    }
  };

  // Voice recording
  const startRecord = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      const chunks = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        const form = new FormData();
        form.append("audio", blob, "speech.webm");
        setThinking(true);
        try {
          const { data } = await axios.post(`${API}/ai/stt`, form, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          if (data.text?.trim()) {
            await sendMessage(data.text.trim());
          } else {
            toast.info("I didn't catch that. Try again.");
            setThinking(false);
          }
        } catch {
          toast.error("Couldn't transcribe.");
          setThinking(false);
        }
      };
      mediaRef.current = rec;
      rec.start();
      setRecording(true);
    } catch {
      toast.error("Microphone permission needed.");
    }
  };

  const stopRecord = () => {
    if (mediaRef.current && mediaRef.current.state !== "inactive") {
      mediaRef.current.stop();
    }
    setRecording(false);
  };

  // IDLE state layout
  if (callState === "idle") {
    return (
      <div className="min-h-screen bg-caos-ambient text-caos-ink p-8 md:p-12 flex flex-col">
        <div className="flex items-center justify-between">
          <div>
            <span className="font-display font-bold tracking-tighter text-caos-forest text-2xl">CAOS</span>
            <span className="font-display font-light text-caos-forest text-2xl">Care</span>
          </div>
          {kiosk && (
            <div className="text-right text-caos-mute text-sm" data-testid="kiosk-label">
              <div className="font-bold">Room {kiosk.room}</div>
              <div>{kiosk.zone}</div>
            </div>
          )}
        </div>

        <div className="flex-1 flex flex-col items-center justify-center text-center max-w-4xl mx-auto">
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute">Welcome</p>
          <h1 className="mt-6 font-display text-5xl md:text-7xl lg:text-[110px] font-light tracking-tighter leading-[0.95] text-caos-forest">
            {resident ? `Hello, ${resident.name.split(" ")[0]}.` : "Hello."}
          </h1>
          <p className="mt-8 text-2xl md:text-3xl text-caos-ink/80 leading-snug">
            If you need help, press the big red button.<br />
            I'll stay with you until someone arrives.
          </p>

          <button
            onClick={() => triggerEmergency("emergency")}
            data-testid="kiosk-emergency-btn"
            aria-label="Emergency call button - press for help"
            className="caos-emergency-btn mt-14 w-full max-w-2xl rounded-[48px] py-16 font-display font-semibold text-5xl md:text-6xl tracking-tight flex items-center justify-center gap-6"
          >
            <Phone className="w-14 h-14 md:w-16 md:h-16" strokeWidth={2.5} />
            CALL FOR HELP
          </button>

          <div className="mt-10 flex flex-wrap gap-6 justify-center">
            <Button
              onClick={() => triggerEmergency("assist")}
              data-testid="kiosk-assist-btn"
              className="caos-kiosk-btn bg-caos-forest hover:bg-caos-forest-hover text-white px-10 rounded-[32px]"
            >
              I need a little help
            </Button>
            <Button
              onClick={() => triggerEmergency("comfort")}
              data-testid="kiosk-chat-btn"
              variant="outline"
              className="caos-kiosk-btn border-2 border-caos-forest text-caos-forest hover:bg-caos-forest hover:text-white bg-white px-10 rounded-[32px]"
            >
              I just want to talk
            </Button>
          </div>
        </div>

        <div className="text-center text-caos-mute text-sm">
          Staff?{" "}
          <button onClick={() => nav("/login")} className="underline hover:text-caos-forest" data-testid="kiosk-staff-link">
            Staff sign in
          </button>
        </div>
      </div>
    );
  }

  // CALLING / WAITING / CHATTING
  return (
    <div className="min-h-screen bg-caos-ambient p-6 md:p-10 flex flex-col">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute">
            {alert?.severity === "emergency" ? "Emergency paged" : "Caregiver paged"}
          </p>
          <h2 className="font-display text-3xl md:text-5xl font-light text-caos-forest mt-2">
            Help is on the way.
          </h2>
          {resident && (
            <p className="text-caos-mute mt-1 text-lg" data-testid="kiosk-resident-name">
              Room {resident.room} · {resident.name}
            </p>
          )}
        </div>
        <Button
          onClick={cancelCall}
          variant="outline"
          data-testid="kiosk-cancel-btn"
          className="rounded-full border-2 border-caos-forest text-caos-forest h-14 px-6 text-lg"
        >
          <X className="w-5 h-5 mr-2" />
          Never mind
        </Button>
      </div>

      {/* AI Orb + transcript */}
      <div className="flex-1 mt-8 grid grid-cols-1 md:grid-cols-12 gap-8">
        {/* Orb */}
        <div className="md:col-span-5 flex items-center justify-center">
          <div className="relative">
            <div
              className={`w-64 h-64 md:w-80 md:h-80 rounded-full ${
                speaking ? "caos-orb-fast" : "caos-orb"
              }`}
              style={{
                background:
                  "radial-gradient(circle at 30% 30%, #4A7C59 0%, #153428 60%, #0E1A14 100%)",
                boxShadow: "0 20px 80px -20px rgba(21, 52, 40, 0.55)",
              }}
              aria-label="AI companion voice"
              data-testid="kiosk-ai-orb"
            />
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-white rounded-full px-5 py-2 border border-caos-line flex items-center gap-2">
              <Volume2 className={`w-4 h-4 ${speaking ? "text-caos-terracotta" : "text-caos-mute"}`} />
              <span className="text-sm font-semibold text-caos-forest">
                {speaking ? "Speaking..." : thinking ? "Thinking..." : "Listening"}
              </span>
            </div>
          </div>
        </div>

        {/* Chat */}
        <div className="md:col-span-7 flex flex-col">
          <Card className="flex-1 bg-white border-caos-line p-6 overflow-y-auto max-h-[50vh]">
            {messages.map((m, i) => (
              <div
                key={i}
                data-testid={`kiosk-msg-${m.role}`}
                className={`mb-5 text-2xl md:text-3xl leading-snug font-display ${
                  m.role === "assistant" ? "text-caos-forest" : "text-caos-ink/70 text-right"
                }`}
              >
                {m.role === "user" && (
                  <span className="text-xs font-bold uppercase tracking-widest text-caos-mute block mb-1">
                    You
                  </span>
                )}
                {m.content}
              </div>
            ))}
            {thinking && (
              <div className="text-caos-mute italic text-xl">CAOS is thinking…</div>
            )}
          </Card>

          <div className="mt-5 flex items-center justify-center gap-4">
            <Button
              onMouseDown={startRecord}
              onMouseUp={stopRecord}
              onTouchStart={startRecord}
              onTouchEnd={stopRecord}
              data-testid="kiosk-mic-btn"
              className={`caos-kiosk-btn !min-h-[100px] w-full rounded-[32px] ${
                recording
                  ? "bg-caos-terracotta hover:bg-caos-terracotta text-white"
                  : "bg-caos-forest hover:bg-caos-forest-hover text-white"
              }`}
            >
              {recording ? (
                <>
                  <MicOff className="w-10 h-10 mr-4" />
                  Release to send
                </>
              ) : (
                <>
                  <Mic className="w-10 h-10 mr-4" />
                  Hold to talk
                </>
              )}
            </Button>
          </div>

          {alert?.severity === "emergency" && (
            <div className="mt-4 bg-caos-terracotta/10 border border-caos-terracotta rounded-2xl p-4 flex items-start gap-3">
              <AlertCircle className="w-6 h-6 text-caos-terracotta mt-0.5" />
              <p className="text-caos-terracotta-dark font-semibold">
                Emergency paged. Stay where you are. A caregiver is coming to you now.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
