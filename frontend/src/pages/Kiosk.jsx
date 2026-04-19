import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { AlertCircle, Mic, MicOff, Volume2, Phone, X, Lightbulb, Fan, Thermometer, Tv, Power } from "lucide-react";
import { toast } from "sonner";

// Kiosk is PUBLIC - no login. Selected/identified by kiosk_id in URL.
// /kiosk/:kioskId  (use "demo" to pick an arbitrary kiosk automatically)

const DEVICE_ICON = { light: Lightbulb, fan: Fan, heater: Thermometer, ac: Thermometer, tv: Tv };

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
  const [autoVoice, setAutoVoice] = useState(false);     // hands-free mode
  const [devices, setDevices] = useState([]);
  const sessionRef = useRef(`sess_${Math.random().toString(36).slice(2)}`);
  const mediaRef = useRef(null);
  const audioRef = useRef(null);
  const seenEmergencyRef = useRef(null);
  const voiceLoopRef = useRef(false);      // is continuous listen loop active?
  const callStateRef = useRef("idle");     // sync callState for async callbacks
  useEffect(() => { callStateRef.current = callState; }, [callState]);

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
        // Load smart devices for this room
        if (data.kiosk?.room) {
          try {
            const { data: allDev } = await axios.get(`${API}/devices/public/by-room/${data.kiosk.room}`);
            setDevices(allDev || []);
          } catch { /* public endpoint may fall back silently */ }
        }
      } catch {
        toast.error("Could not load kiosk");
      }
    })();
  }, [kioskId]);

  // Poll for incoming emergencies (panic-press / fall) → auto hands-free
  useEffect(() => {
    if (!kiosk?.kiosk_id) return;
    let stop = false;
    const poll = async () => {
      try {
        const { data } = await axios.get(`${API}/kiosks/${kiosk.kiosk_id}/active-emergency`);
        if (stop) return;
        const a = data.alert;
        if (a && a.alert_id !== seenEmergencyRef.current && callStateRef.current === "idle") {
          seenEmergencyRef.current = a.alert_id;
          handleIncomingEmergency(a);
        }
      } catch { /* silent */ }
    };
    poll();
    const t = setInterval(poll, 3000);
    return () => { stop = true; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kiosk]);

  // Watch for the current alert being resolved by staff → quietly end voice loop
  useEffect(() => {
    if (!alert?.alert_id) return;
    const t = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/alerts/${alert.alert_id}`);
        if (data.status === "resolved") {
          voiceLoopRef.current = false;
          await speak("A caregiver is with you now. I'll step back.");
          setTimeout(() => cancelCall(), 500);
        }
      } catch { /* silent */ }
    }, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alert?.alert_id]);

  const handleIncomingEmergency = async (a) => {
    setAlert(a);
    setAutoVoice(true);
    setCallState("chatting");
    const name = (a.resident_name || resident?.name || "there").split(" ")[0];
    const line = a.press_count >= 2
      ? `I'm here, ${name}. I've called for help — they're on their way. Stay with me. Tell me what's happening.`
      : `I'm here, ${name}. I've paged a caregiver. Can you tell me what you need?`;
    setMessages([{ role: "assistant", content: line }]);
    await speak(line);
    // Start the continuous loop (auto listen → transcribe → reply → repeat)
    voiceLoopRef.current = true;
    runVoiceLoop();
  };

  // ---------- Continuous voice loop (hands-free) ----------
  // Plays a short beep so blind residents know it's listening.
  const playBeep = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.value = 0.15;
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      setTimeout(() => { osc.stop(); ctx.close(); }, 150);
    } catch { /* noop */ }
  };

  // Listen for up to 8s, resolve blob (or null on abort).
  const listenOnce = () =>
    new Promise(async (resolve) => {
      try {
        if (!voiceLoopRef.current) return resolve(null);
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
        const chunks = [];
        let settled = false;
        const done = (blob) => {
          if (settled) return;
          settled = true;
          stream.getTracks().forEach((t) => t.stop());
          setRecording(false);
          resolve(blob);
        };
        rec.ondataavailable = (e) => chunks.push(e.data);
        rec.onstop = () => done(new Blob(chunks, { type: "audio/webm" }));
        mediaRef.current = rec;
        rec.start();
        setRecording(true);
        setTimeout(() => {
          if (rec.state !== "inactive") rec.stop();
        }, 8000);
      } catch {
        toast.error("Microphone permission needed for hands-free.");
        resolve(null);
      }
    });

  const runVoiceLoop = async () => {
    // Keep going until voiceLoopRef flipped off (cancel / alert resolved)
    let emptyRounds = 0;
    while (voiceLoopRef.current && callStateRef.current !== "idle") {
      playBeep();
      const blob = await listenOnce();
      if (!voiceLoopRef.current) break;
      if (!blob || blob.size < 1500) {
        emptyRounds++;
        if (emptyRounds === 1) {
          await speak("I'm still here. Take your time.");
          continue;
        }
        if (emptyRounds >= 3) {
          // No response after 3 tries — stop politely but keep alert open
          await speak("I'll wait quietly. Press the button or speak when you need me.");
          break;
        }
        continue;
      }
      emptyRounds = 0;
      const form = new FormData();
      form.append("audio", blob, "speech.webm");
      setThinking(true);
      let text = "";
      try {
        const { data } = await axios.post(`${API}/ai/stt`, form, { headers: { "Content-Type": "multipart/form-data" } });
        text = (data.text || "").trim();
      } catch { /* ignore */ }
      setThinking(false);
      if (!voiceLoopRef.current) break;
      if (!text) continue;

      // Exit phrase heuristic
      const lower = text.toLowerCase();
      const exitKeywords = ["i'm fine", "i am fine", "never mind", "nevermind", "that's all", "thats all", "thank you goodbye", "all done", "i'm okay", "im okay"];
      const wantsExit = exitKeywords.some((k) => lower.includes(k));

      await sendMessage(text);
      if (wantsExit) {
        await speak("Alright. I'll let you rest. A caregiver is still on the way.");
        break;
      }
    }
    voiceLoopRef.current = false;
  };

  const startContinuousListen = () => {
    // Legacy shim for older callers — just kick off the loop
    voiceLoopRef.current = true;
    runVoiceLoop();
  };

  // Medication reminder polling — only when idle
  useEffect(() => {
    if (!kiosk?.room) return;
    let stop = false;
    const checkMeds = async () => {
      if (callStateRef.current !== "idle") return;
      try {
        const { data: due } = await axios.get(`${API}/medications/due/by-room/${kiosk.room}`);
        if (stop || !due || due.length === 0) return;
        const m = due[0];
        const name = (resident?.preferred_name || resident?.name || "there").split(" ")[0];
        const line = `Hi ${name}, it's time for your ${m.title}.${m.dose_notes ? " " + m.dose_notes + "." : ""} If you need help, press the red button.`;
        await speak(line);
        await axios.post(`${API}/medications/ack/${m.reminder_id}`).catch(() => {});
        toast.success(`Reminder spoken: ${m.title}`);
      } catch { /* silent */ }
    };
    checkMeds();
    const t = setInterval(checkMeds, 60000);
    return () => { stop = true; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kiosk, resident]);

  const speak = (text) =>
    new Promise(async (resolve) => {
      try {
        setSpeaking(true);
        const { data } = await axios.post(`${API}/ai/tts`, { text, voice: "sage" });
        const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
        audioRef.current = audio;
        audio.onended = () => { setSpeaking(false); resolve(); };
        audio.onerror = () => { setSpeaking(false); resolve(); };
        await audio.play();
      } catch {
        setSpeaking(false);
        resolve();
      }
    });

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
      setAutoVoice(true);
      setCallState("chatting");
      const name = resident?.preferred_name || resident?.name?.split(" ")[0] || "there";
      const line = severity === "emergency"
        ? `Hello ${name}. Help is on the way. Stay where you are. I am here with you. Tell me what's happening.`
        : `Hello ${name}. I've paged a caregiver. While we wait, what can I help with?`;
      setMessages([{ role: "assistant", content: line }]);
      await speak(line);
      voiceLoopRef.current = true;
      runVoiceLoop();
    } catch {
      toast.error("Could not send the call. Please try again.");
      setCallState("idle");
    }
  };

  const cancelCall = async () => {
    voiceLoopRef.current = false;
    if (mediaRef.current && mediaRef.current.state !== "inactive") {
      try { mediaRef.current.stop(); } catch {}
    }
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch {}
    }
    setAlert(null);
    setMessages([]);
    setCallState("idle");
    setSpeaking(false);
    setAutoVoice(false);
    setRecording(false);
    setThinking(false);
  };

  const sendDeviceCommand = async (action, value) => {
    if (!kiosk?.room) return;
    try {
      await axios.post(`${API}/devices/public/room/${kiosk.room}/command`, { action, value });
      toast.success(`${action} → ${value}`);
      // Refresh device state
      try {
        const { data: allDev } = await axios.get(`${API}/devices/public/by-room/${kiosk.room}`);
        setDevices(allDev || []);
      } catch { /* ignore */ }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Couldn't reach the device");
    }
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
      await speak(data.reply);
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

          {/* Smart-room controls */}
          {devices.length > 0 && (
            <div className="mt-14 w-full max-w-3xl" data-testid="kiosk-device-panel">
              <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute mb-4">Your room</p>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {devices.map((d) => {
                  const Icon = DEVICE_ICON[d.kind] || Power;
                  const isOn = d.state?.power === "on";
                  return (
                    <button
                      key={d.device_id}
                      data-testid={`kiosk-dev-${d.device_id}`}
                      onClick={() => sendDeviceCommand("power", isOn ? "off" : "on")}
                      className={`rounded-3xl border-2 p-5 flex flex-col items-start gap-2 transition-all ${
                        isOn
                          ? "bg-caos-forest text-white border-caos-forest shadow-lg"
                          : "bg-white text-caos-forest border-caos-line hover:border-caos-forest"
                      }`}
                    >
                      <Icon className="w-8 h-8" strokeWidth={2} />
                      <span className="font-display text-lg font-semibold leading-tight text-left">
                        {d.label.replace(`Room ${kiosk.room} `, "")}
                      </span>
                      <span className={`text-xs font-bold uppercase tracking-wider ${isOn ? "text-white/80" : "text-caos-mute"}`}>
                        {isOn ? "On — tap to turn off" : "Off — tap to turn on"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
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
            {autoVoice ? "Panic-press detected — hands-free" : alert?.severity === "emergency" ? "Emergency paged" : "Caregiver paged"}
          </p>
          <h2 className="font-display text-3xl md:text-5xl font-light text-caos-forest mt-2">
            Help is on the way.
          </h2>
          {resident && (
            <p className="text-caos-mute mt-1 text-lg" data-testid="kiosk-resident-name">
              Room {resident.room} · {resident.name}
            </p>
          )}
          {autoVoice && (
            <p className="mt-2 inline-flex items-center gap-2 bg-caos-terracotta/10 text-caos-terracotta-dark border border-caos-terracotta rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider" data-testid="kiosk-autovoice-banner">
              <Mic className="w-3 h-3" /> Auto-listening · you don't have to touch anything
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
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-white rounded-full px-5 py-2 border border-caos-line flex items-center gap-2" data-testid="kiosk-voice-status">
              <Volume2 className={`w-4 h-4 ${speaking ? "text-caos-terracotta" : recording ? "text-caos-moss" : "text-caos-mute"}`} />
              <span className="text-sm font-semibold text-caos-forest">
                {speaking ? "Speaking..." : recording ? "Listening..." : thinking ? "Thinking..." : "Ready"}
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
