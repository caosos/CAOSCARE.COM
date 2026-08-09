import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { AlertCircle, Mic, Volume2, Phone, Lightbulb, Fan, Thermometer, Tv, Power, Type, Contrast, Play } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import RealtimeChatScreen from "./RealtimeChatScreen";

// Kiosk is PUBLIC - no login. Selected/identified by kiosk_id in URL.
// /kiosk/:kioskId  (use "demo" to pick an arbitrary kiosk automatically)
//
// 2026-08-09: retired the legacy turn-based (STT -> /api/ai/chat -> TTS)
// voice loop and its "Live"/"Turn" toggle. Full-duplex Realtime (WebRTC)
// via RealtimeChatScreen is now the only resident conversation path - see
// docs/ARIA_VOICE_FIRST.md for why (the two paths had independently
// drifted prompts, which was the actual root cause of a real user-facing
// bug). Medication reminders, which used to piggyback on the legacy
// speak() helper, now use the mode-independent announceLine() below so
// that feature has no gap from this change.

const DEVICE_ICON = { light: Lightbulb, fan: Fan, heater: Thermometer, ac: Thermometer, tv: Tv };

export default function Kiosk() {
  const { kioskId } = useParams();
  const nav = useNavigate();

  const [kiosk, setKiosk] = useState(null);
  const [resident, setResident] = useState(null);
  const [callState, setCallState] = useState("idle"); // idle | calling | waiting | chatting
  const [alert, setAlert] = useState(null);
  const [devices, setDevices] = useState([]);
  const [micReady, setMicReady] = useState(false);       // user gesture received + mic permission granted
  const [needsTap, setNeedsTap] = useState(false);       // remote pendant fired but we need a user tap first (autoplay/mic policy)
  const [pendingAlert, setPendingAlert] = useState(null);
  const audioCtxRef = useRef(null);
  const seenEmergencyRef = useRef(null);
  const callStateRef = useRef("idle");     // sync callState for async callbacks
  useEffect(() => { callStateRef.current = callState; }, [callState]);

  // Accessibility — text-size & high-contrast per kiosk, persisted so a room
  // set for a low-vision resident stays that way across reboots.
  const [textSize, setTextSize] = useState(() => localStorage.getItem("caos_kiosk_textsize") || "md"); // md | lg | xl
  const [highContrast, setHighContrast] = useState(() => localStorage.getItem("caos_kiosk_hc") === "1");
  useEffect(() => { localStorage.setItem("caos_kiosk_textsize", textSize); }, [textSize]);
  useEffect(() => { localStorage.setItem("caos_kiosk_hc", highContrast ? "1" : "0"); }, [highContrast]);
  const cycleTextSize = () => setTextSize((s) => (s === "md" ? "lg" : s === "lg" ? "xl" : "md"));
  const a11yRootClass = `${textSize === "lg" ? "kiosk-text-lg" : textSize === "xl" ? "kiosk-text-xl" : ""} ${highContrast ? "kiosk-hc" : ""}`.trim();

  // Voice preference (OpenAI TTS voice). Persisted per-kiosk so each room
  // can match its resident's preference.
  const VOICES = [
    { id: "shimmer", label: "Shimmer", desc: "Soft & gentle" },
    { id: "coral",   label: "Coral",   desc: "Warm & inviting" },
    { id: "nova",    label: "Nova",    desc: "Bright & kind" },
    { id: "sage",    label: "Sage",    desc: "Articulate & refined" },
    { id: "fable",   label: "Fable",   desc: "Storytelling warmth" },
    { id: "ballad",  label: "Ballad",  desc: "Melodic & thoughtful" },
    { id: "alloy",   label: "Alloy",   desc: "Neutral & clear" },
    { id: "ash",     label: "Ash",     desc: "Deeper, calming" },
    { id: "onyx",    label: "Onyx",    desc: "Deep & reassuring" },
    { id: "echo",    label: "Echo",    desc: "Crisp & even" },
    { id: "verse",   label: "Verse",   desc: "Expressive & friendly" },
  ];
  const [voiceId, setVoiceId] = useState(() => localStorage.getItem("caos_kiosk_voice") || "shimmer");
  const voiceIdRef = useRef(voiceId);
  useEffect(() => {
    voiceIdRef.current = voiceId;
    localStorage.setItem("caos_kiosk_voice", voiceId);
  }, [voiceId]);
  const [voicePickerOpen, setVoicePickerOpen] = useState(false);

  // TVs-were-muted tracking: when a voice call begins we auto-mute any TV
  // in the room so the mic doesn't pick up Wheel of Fortune dialogue as
  // resident speech. On call end, we restore the prior power state.
  const mutedDevicesRef = useRef([]); // [{ device_id, prior_power }]

  // Prime browser audio + mic permission on the first user click.
  // Without a user gesture, Chrome will silently block both TTS playback and getUserMedia.
  // Note: when running inside a cross-origin iframe (e.g. the Emergent preview pane),
  // Chrome rejects getUserMedia synchronously unless the parent tag sets
  // allow="microphone". We detect that case and offer a "open in full tab" escape.
  const inSandboxedIframe = () => {
    try { return window.self !== window.top; } catch { return true; }
  };

  const openInFullTab = () => {
    try { window.open(window.location.href, "_blank", "noopener"); } catch { /* ignore */ }
  };

  const primeMedia = async () => {
    if (micReady) return true;
    try {
      // Unlock AudioContext for playback (announcements, RealtimeChatScreen audio)
      if (!audioCtxRef.current) {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        audioCtxRef.current = new Ctx();
        if (audioCtxRef.current.state === "suspended") await audioCtxRef.current.resume();
      }
      // Ask for mic access and immediately release the stream (Realtime's own
      // WebRTC setup re-acquires it when the call actually starts)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setMicReady(true);
      return true;
    } catch (e) {
      // Iframe sandbox = no prompt, direct NotAllowedError. Give the user a way out.
      if (inSandboxedIframe()) {
        toast.error("This preview frame can't ask for your mic. Tap to open in a full tab.", {
          duration: 8000,
          action: { label: "Open full tab", onClick: openInFullTab },
        });
      } else {
        toast.error("Microphone permission needed. Please allow it in your browser.");
      }
      return false;
    }
  };

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
        const { data } = await axios.get(`${API}/alerts/public/${alert.alert_id}/status`);
        if (data.status === "resolved") {
          // The WebRTC loop owns hearing/speaking during a call - it owns the
          // goodbye too. Just close the call silently.
          setTimeout(() => cancelCall(), 500);
        }
      } catch { /* silent */ }
    }, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alert?.alert_id]);

  const handleIncomingEmergency = async (a) => {
    setAlert(a);
    // If the browser hasn't received a user gesture yet, we cannot play audio
    // or open the mic. Defer until the user taps anywhere.
    if (!micReady) {
      setPendingAlert(a);
      setNeedsTap(true);
      setCallState("waiting");
      return;
    }
    await beginConversation(a);
  };

  const beginConversation = async (a) => {
    setCallState("chatting");
    // Auto-mute any TVs or loud audio devices in the room so the mic
    // doesn't pick them up as resident speech. Restore on call end.
    mutedDevicesRef.current = [];
    try {
      const noisy = (devices || []).filter((d) => (d.kind === "tv" || d.kind === "speaker") && d.state?.power === "on");
      for (const d of noisy) {
        try {
          await axios.post(`${API}/devices/public/room/${kiosk.room}/command`, { action: "power", value: "off" });
          mutedDevicesRef.current.push({ device_id: d.device_id, prior_power: "on" });
        } catch { /* ignore */ }
      }
    } catch { /* ignore */ }
    // RealtimeChatScreen owns its own greeting + listening loop from here.
  };

  // Non-conversational, mode-independent single-line TTS announcement.
  // Used for medication reminders - NOT part of any conversation, so it
  // doesn't need (and shouldn't use) the full-duplex Realtime peer
  // connection; a plain TTS clip is the right tool for "say this one thing."
  // Only ever called while callState is idle (see checkMeds below), so there
  // is no active RealtimeChatScreen session to conflict with.
  const announceLine = (text) =>
    new Promise((resolve) => {
      (async () => {
        try {
          const { data } = await axios.post(`${API}/ai/tts`, { text, voice: voiceIdRef.current }, { timeout: 8000 });
          const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
          audio.onended = () => resolve();
          audio.onerror = () => resolve();
          await audio.play();
        } catch {
          resolve();
        }
      })();
    });

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
        await announceLine(line);
        await axios.post(`${API}/medications/ack/${m.reminder_id}`).catch(() => {});
        toast.success(`Reminder spoken: ${m.title}`);
      } catch { /* silent */ }
    };
    checkMeds();
    const t = setInterval(checkMeds, 60000);
    return () => { stop = true; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kiosk, resident]);

  const triggerEmergency = async (severity = "emergency") => {
    if (!kiosk) return;
    // A real user tap — prime audio+mic so the call can actually connect
    const ok = await primeMedia();
    if (!ok) return;
    setCallState("calling");
    try {
      const { data } = await axios.post(`${API}/alerts`, {
        kiosk_id: kiosk.kiosk_id,
        severity,
        message: severity === "emergency" ? "Emergency button pressed" : "Assistance requested",
        triggered_by: "kiosk_button",
      });
      setAlert(data);
      setCallState("chatting");
      // RealtimeChatScreen owns the greeting + conversation from here.
    } catch {
      toast.error("Could not send the call. Please try again.");
      setCallState("idle");
    }
  };

  const cancelCall = async () => {
    // Restore any TVs/speakers we muted when the call began.
    if (mutedDevicesRef.current.length) {
      for (const m of mutedDevicesRef.current) {
        if (m.prior_power === "on") {
          try {
            await axios.post(`${API}/devices/public/room/${kiosk.room}/command`, { action: "power", value: "on" });
          } catch { /* ignore */ }
        }
      }
      mutedDevicesRef.current = [];
    }
    setAlert(null);
    setCallState("idle");
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

  // IDLE state layout
  // Voice picker dialog — rendered in BOTH the idle and chat return blocks
  // so the user can change voices from any state.
  const voicePickerDialog = (
    <Dialog open={voicePickerOpen} onOpenChange={setVoicePickerOpen}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl text-caos-forest">Choose Aria's voice</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-caos-mute mb-4">
          Tap ▶ to preview. Tap the name to select. The voice is remembered per kiosk.
        </p>
        <div className="space-y-2">
          {VOICES.map((v) => {
            const selected = voiceId === v.id;
            return (
              <div
                key={v.id}
                className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all ${
                  selected ? "border-caos-forest bg-caos-forest/5" : "border-caos-line hover:border-caos-forest"
                }`}
                data-testid={`voice-row-${v.id}`}
              >
                <button
                  onClick={async () => {
                    try {
                      const { data } = await axios.post(`${API}/ai/tts`, {
                        text: "Hello. This is how I sound. I'll be right here with you.",
                        voice: v.id,
                      }, { timeout: 10000 });
                      const a = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
                      await a.play();
                    } catch { toast.error("Couldn't preview this voice"); }
                  }}
                  data-testid={`voice-preview-${v.id}`}
                  className="w-10 h-10 rounded-full bg-caos-forest text-white flex items-center justify-center hover:bg-caos-forest-hover flex-shrink-0"
                  aria-label={`Preview ${v.label}`}
                >
                  <Play className="w-4 h-4" />
                </button>
                <button
                  onClick={() => { setVoiceId(v.id); toast.success(`Voice set to ${v.label}`); }}
                  data-testid={`voice-select-${v.id}`}
                  className="flex-1 text-left"
                >
                  <div className="font-display font-medium text-caos-forest text-lg">
                    {v.label} {selected && <span className="ml-2 text-xs font-bold uppercase tracking-widest text-caos-forest/70">★ selected</span>}
                  </div>
                  <div className="text-sm text-caos-mute">{v.desc}</div>
                </button>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-caos-mute italic mt-4 border-t border-caos-line pt-3">
          Note: The available voices above are the supported kiosk voices for this deployment.
        </p>
      </DialogContent>
    </Dialog>
  );

  if (callState === "idle") {
    return (
      <div className={`min-h-screen bg-caos-ambient text-caos-ink p-8 md:p-12 flex flex-col ${a11yRootClass}`}>
        {inSandboxedIframe() && (
          <button
            onClick={openInFullTab}
            data-testid="kiosk-iframe-warning"
            className="mb-4 rounded-2xl border-2 border-caos-amber bg-caos-amber/10 px-4 py-3 text-left flex items-center gap-3 hover:bg-caos-amber/20 transition-colors"
            title="Voice features require a full browser tab"
          >
            <AlertCircle className="w-5 h-5 text-caos-amber shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-caos-forest text-sm">Voice features need a full browser tab</p>
              <p className="text-caos-mute text-xs">The preview pane can't request microphone access. Tap here to open the kiosk in a real tab — then the browser will prompt for mic permission as usual.</p>
            </div>
            <span className="text-xs font-bold uppercase tracking-widest text-caos-forest shrink-0">Open →</span>
          </button>
        )}
        <div className="flex items-center justify-between">
          <div>
            <span className="font-display font-bold tracking-tighter text-caos-forest text-2xl">CAOS</span>
            <span className="font-display font-light text-caos-forest text-2xl">Care</span>
          </div>
          <div className="flex items-center gap-2 kiosk-a11y-row">
            <button
              onClick={cycleTextSize}
              data-testid="kiosk-a11y-text-size"
              aria-label={`Text size: ${textSize}. Tap to cycle.`}
              title="Text size"
              className="px-3 py-2 rounded-full bg-white border border-caos-line text-caos-forest hover:bg-caos-forest hover:text-white flex items-center gap-1 text-sm font-bold uppercase tracking-wider"
            >
              <Type className="w-4 h-4" /> {textSize === "md" ? "A" : textSize === "lg" ? "A+" : "A++"}
            </button>
            <button
              onClick={() => setVoicePickerOpen(true)}
              data-testid="kiosk-a11y-voice"
              aria-label={`Voice: ${voiceId}. Tap to change voice.`}
              title="Change Aria's voice"
              className="px-4 py-2 rounded-full bg-caos-forest text-white hover:bg-caos-forest-hover flex items-center gap-2 text-sm font-bold uppercase tracking-wider shadow-sm"
            >
              <Volume2 className="w-4 h-4" />
              <span className="opacity-80">Voice:</span>
              <span>{voiceId}</span>
            </button>
            <button
              onClick={() => setHighContrast((v) => !v)}
              data-testid="kiosk-a11y-contrast"
              aria-label={`High contrast mode ${highContrast ? "on" : "off"}. Tap to toggle.`}
              title="High contrast"
              aria-pressed={highContrast}
              className={`px-3 py-2 rounded-full border flex items-center gap-1 text-sm font-bold uppercase tracking-wider ${
                highContrast
                  ? "bg-caos-forest text-white border-caos-forest"
                  : "bg-white text-caos-forest border-caos-line hover:bg-caos-forest hover:text-white"
              }`}
            >
              <Contrast className="w-4 h-4" /> {highContrast ? "HC on" : "HC"}
            </button>
            {kiosk && (
              <div className="text-right text-caos-mute text-sm ml-2" data-testid="kiosk-label">
                <div className="font-bold">Room {kiosk.room}</div>
                <div>{kiosk.zone}</div>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 flex flex-col items-center justify-center text-center max-w-4xl mx-auto">
          <p className="text-[10px] md:text-xs font-bold uppercase tracking-[0.32em] text-caos-mute">
            CARE · powered by CAOS
          </p>
          <h1 className="kiosk-hello mt-5 font-display text-5xl md:text-7xl lg:text-[110px] font-light tracking-tighter leading-[0.95] text-caos-forest">
            {resident ? `Hello, ${resident.name.split(" ")[0]}.` : "Hello."}
          </h1>
          <p className="kiosk-prompt mt-6 text-2xl md:text-3xl text-caos-ink/80 leading-snug">
            If you need help, press the big red button.<br />
            I'll stay with you while staff are notified.
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
              <Phone className="w-6 h-6 mr-3" /> I need a little help
            </Button>
            <Button
              onClick={() => triggerEmergency("comfort")}
              data-testid="kiosk-chat-btn"
              variant="outline"
              className="caos-kiosk-btn border-2 border-caos-forest text-caos-forest hover:bg-caos-forest hover:text-white bg-white px-10 rounded-[32px]"
            >
              <Mic className="w-6 h-6 mr-3" /> I just want to talk
            </Button>
          </div>
          {!micReady && (
            <p className="mt-4 text-sm text-caos-mute italic" data-testid="kiosk-mic-prime-hint">
              Tap any button above — the tablet will ask for microphone permission once, then the voice is hands-free.
            </p>
          )}

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

        {/* Voice picker dialog — shared with chat state via voicePickerDialog */}
        {voicePickerDialog}
      </div>
    );
  }

  // CALLING / WAITING / CHATTING
  // Full-duplex Realtime (WebRTC) is the only resident conversation path.
  // Calling+waiting are skipped because the realtime peer connection
  // establishes in under a second.
  return (
    <>
      <RealtimeChatScreen
        resident={resident}
        kiosk={kiosk}
        voiceId={voiceId}
        a11yRootClass={a11yRootClass}
        onOpenVoicePicker={() => setVoicePickerOpen(true)}
        onEnd={() => {
          setCallState("idle");
          setAlert(null);
        }}
      />
      {voicePickerDialog}

      {/* Tap-to-answer overlay when remote pendant fired but we have no user gesture yet */}
      {needsTap && (
        <button
          data-testid="kiosk-tap-to-answer"
          onClick={async () => {
            const ok = await primeMedia();
            if (!ok) return;
            setNeedsTap(false);
            const a = pendingAlert;
            setPendingAlert(null);
            if (a) await beginConversation(a);
          }}
          className="fixed inset-0 z-50 bg-caos-forest/95 text-white flex flex-col items-center justify-center gap-6 p-8 cursor-pointer"
        >
          <div className="animate-pulse">
            <Phone className="w-24 h-24" />
          </div>
          <p className="font-display text-5xl md:text-7xl font-light text-center">Incoming call</p>
          <p className="text-2xl md:text-3xl text-center max-w-2xl">
            {(pendingAlert?.resident_name || resident?.name || "A resident")} pressed their pendant.
          </p>
          <p className="text-xl uppercase tracking-[0.3em] text-caos-amber mt-4">TAP ANYWHERE TO ANSWER</p>
        </button>
      )}
      {alert?.severity === "emergency" && callState === "chatting" && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 bg-caos-terracotta/10 border border-caos-terracotta rounded-2xl p-4 flex items-start gap-3 max-w-md">
          <AlertCircle className="w-6 h-6 text-caos-terracotta mt-0.5" />
          <p className="text-caos-terracotta-dark font-semibold">
            Emergency paged. Stay where you are. Staff have been notified.
          </p>
        </div>
      )}
    </>
  );
}
