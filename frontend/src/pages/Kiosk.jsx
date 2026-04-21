import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { AlertCircle, Mic, MicOff, Volume2, Phone, X, Lightbulb, Fan, Thermometer, Tv, Power, Type, Contrast, Sparkles, Play } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

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
  const [micReady, setMicReady] = useState(false);       // user gesture received + mic permission granted
  const [needsTap, setNeedsTap] = useState(false);       // remote pendant fired but we need a user tap first (autoplay/mic policy)
  const [pendingAlert, setPendingAlert] = useState(null);
  const sessionRef = useRef(`sess_${Math.random().toString(36).slice(2)}`);
  const mediaRef = useRef(null);
  const audioRef = useRef(null);
  const audioCtxRef = useRef(null);
  const seenEmergencyRef = useRef(null);
  const voiceLoopRef = useRef(false);      // is continuous listen loop active?
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

  // Sleep-mode — resident said something like "I'll just sit and wait".
  const [sleeping, setSleeping] = useState(false);
  const sleepingRef = useRef(false);
  useEffect(() => { sleepingRef.current = sleeping; }, [sleeping]);

  // TVs-were-muted tracking: when a voice call begins we auto-mute any TV
  // in the room so the mic doesn't pick up Wheel of Fortune dialogue as
  // resident speech. On call end, we restore the prior power state.
  const mutedDevicesRef = useRef([]); // [{ device_id, prior_power }]

  // Prime browser audio + mic permission on the first user click.
  // Without a user gesture, Chrome will silently block both TTS playback and getUserMedia.
  const primeMedia = async () => {
    if (micReady) return true;
    try {
      // Unlock AudioContext for beep
      if (!audioCtxRef.current) {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        audioCtxRef.current = new Ctx();
        if (audioCtxRef.current.state === "suspended") await audioCtxRef.current.resume();
      }
      // Ask for mic access and immediately release the stream (we'll re-acquire per utterance)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setMicReady(true);
      return true;
    } catch (e) {
      toast.error("Microphone permission needed. Please allow it in your browser.");
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
  // Plays a short beep so blind residents know it's listening. Suppressed
  // when CAOS is sleeping (resident asked to sit in silence).
  const playBeep = () => {
    if (sleepingRef.current) return;
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

  // Post-hoc RMS analysis — any recording whose average audio energy is
  // below this threshold is treated as "silence or background noise"
  // (e.g. TV at low volume, hallway chatter). Prevents Whisper from
  // dutifully transcribing TV dialogue and CAOS replying to it.
  const ACTIVE_RMS = 0.018;   // clear resident speech sits around 0.03-0.1
  const computeRms = async (blob) => {
    try {
      const buf = await blob.arrayBuffer();
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const actx = new Ctx();
      const audioBuf = await actx.decodeAudioData(buf);
      const ch = audioBuf.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < ch.length; i++) sum += ch[i] * ch[i];
      try { actx.close(); } catch {}
      return Math.sqrt(sum / Math.max(ch.length, 1));
    } catch {
      return 1; // on decode failure, assume speech — don't starve the loop
    }
  };

  // Listen for up to ~14s per turn. Elderly speech pace is slower — 8s
  // was cutting residents off mid-sentence.
  const LISTEN_MS = 14000;
  const MIN_BLOB_BYTES = 800; // quieter voices still count as speech
  const listenOnce = () =>
    new Promise(async (resolve) => {
      if (!voiceLoopRef.current) return resolve(null);
      let stream = null;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        voiceLoopRef.current = false;
        toast.error("Microphone permission needed.");
        return resolve(null);
      }
      try {
        const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
        const chunks = [];
        let settled = false;
        const done = (blob) => {
          if (settled) return;
          settled = true;
          try { stream.getTracks().forEach((t) => t.stop()); } catch {}
          setRecording(false);
          resolve(blob);
        };
        rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
        rec.onstop = () => done(new Blob(chunks, { type: "audio/webm" }));
        rec.onerror = () => done(null);
        mediaRef.current = rec;
        rec.start(250); // emit chunks every 250ms so we never end up with an empty blob
        setRecording(true);
        setTimeout(() => {
          try { if (rec.state !== "inactive") rec.stop(); } catch {}
        }, LISTEN_MS);
      } catch {
        try { stream.getTracks().forEach((t) => t.stop()); } catch {}
        setRecording(false);
        resolve(null);
      }
    });

  // Intent phrases — unambiguous signals that the resident wants CAOS to
  // stop talking for now but stay available. Hitting any of these makes
  // CAOS say one short acknowledgment and fully enter sleep mode.
  const SLEEP_INTENT_PATTERNS = [
    "i'll just wait", "ill just wait", "i will just wait",
    "i'll just sit", "ill just sit", "i will just sit",
    "just sit here", "i'm going to sit", "im going to sit",
    "just wait for", "wait for somebody", "wait for someone",
    "wait for help", "wait for the nurse", "wait for the caregiver",
    "sit quietly", "sit with me quietly", "be quiet for a bit",
    "stop talking for now", "no more talking", "no more questions for now",
    "i don't need to talk", "i dont need to talk", "i do not need to talk",
    "i don't want to talk", "i dont want to talk",
    "shh", "hush",
  ];
  // Hard exits — resident wants CAOS gone AND the alert ended on their end.
  const EXIT_INTENT_PATTERNS = [
    "goodbye caos", "bye caos", "stop listening",
    "leave me alone", "that's all i need", "that is all i need",
    "i'm done talking", "im done talking", "i am done talking",
  ];

  const runVoiceLoop = async () => {
    // Keep going until voiceLoopRef flipped off (cancel / alert resolved /
    // entered sleep). Empty-round tolerance is deliberately generous.
    let emptyRounds = 0;
    while (voiceLoopRef.current && callStateRef.current !== "idle") {
      if (sleepingRef.current) break;
      playBeep();
      const blob = await listenOnce();
      if (!voiceLoopRef.current || sleepingRef.current) break;
      // Energy gate — filters out TV, hallway noise, or very quiet ambient.
      let rms = 0;
      if (blob && blob.size >= MIN_BLOB_BYTES) {
        rms = await computeRms(blob);
      }
      const speechDetected = blob && blob.size >= MIN_BLOB_BYTES && rms >= ACTIVE_RMS;
      if (!speechDetected) {
        emptyRounds++;
        if (emptyRounds === 2) { await speak("I'm still here. Take your time."); continue; }
        if (emptyRounds === 4) { await speak("No rush. I'll stay with you."); continue; }
        if (emptyRounds >= 6) {
          // Long silence → gently step into sleep mode, don't walk off.
          await speak("Okay. I'll be right here if you need me.");
          sleepingRef.current = true;
          setSleeping(true);
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

      const lower = text.toLowerCase();

      // Sleep-intent — resident wants silence but not to end the alert.
      if (SLEEP_INTENT_PATTERNS.some((k) => lower.includes(k))) {
        await speak("Okay. I'll be right here if you need me.");
        sleepingRef.current = true;
        setSleeping(true);
        break;
      }
      // Hard exit — resident clearly done conversing.
      if (EXIT_INTENT_PATTERNS.some((k) => lower.includes(k))) {
        await sendMessage(text);
        await speak("Alright. I'll let you rest. A caregiver is still on the way.");
        break;
      }

      // Normal path — Claude processes the message. sendMessage also
      // auto-enters sleep mode if Claude's OWN reply signals rest intent
      // ("I'll be quiet", "I'll be right here", "just rest", etc).
      await sendMessage(text);
      if (sleepingRef.current) break;
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

  const speakFallback = (text) =>
    new Promise((resolve) => {
      try {
        if (!("speechSynthesis" in window)) return resolve();
        const u = new SpeechSynthesisUtterance(text);
        u.rate = 0.95;
        u.pitch = 1.0;
        u.onend = () => resolve();
        u.onerror = () => resolve();
        window.speechSynthesis.speak(u);
      } catch { resolve(); }
    });

  const speak = (text) =>
    new Promise(async (resolve) => {
      try {
        setSpeaking(true);
        const { data } = await axios.post(`${API}/ai/tts`, { text, voice: voiceIdRef.current }, { timeout: 8000 });
        const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
        audioRef.current = audio;
        audio.onended = () => { setSpeaking(false); resolve(); };
        audio.onerror = async () => {
          // Fallback: browser TTS so the resident never hears silence
          await speakFallback(text);
          setSpeaking(false);
          resolve();
        };
        await audio.play();
      } catch {
        // Network / API down → canned local voice
        await speakFallback(text);
        setSpeaking(false);
        resolve();
      }
    });

  const triggerEmergency = async (severity = "emergency") => {
    if (!kiosk) return;
    // A real user tap — prime audio+mic so the loop actually works
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
    setMessages([]);
    setCallState("idle");
    setSpeaking(false);
    setAutoVoice(false);
    setRecording(false);
    setThinking(false);
    setSleeping(false);
  };

  // Wake CAOS from sleep mode without creating a new alert. Resident taps
  // the big "Tap to talk again" button on the chat screen.
  const wakeFromSleep = async () => {
    if (!sleepingRef.current) return;
    setSleeping(false);
    voiceLoopRef.current = true;
    await speak("I'm here.");
    runVoiceLoop();
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

  // Canned comfort lines used when Claude is unreachable. Rotates so the
  // resident doesn't hear the same sentence every time.
  const OFFLINE_LINES = [
    "I'm here with you. Help is on the way. Just breathe — slow and easy.",
    "Stay right where you are. A caregiver is coming to you now. I'm not going anywhere.",
    "You're not alone. Someone will be there very soon. I'll wait with you.",
    "Take your time. Help is on its way. I'm listening.",
  ];
  const offlineCursorRef = useRef(0);

  const sendMessage = async (text) => {
    const userMsg = { role: "user", content: text };
    setMessages((m) => [...m, userMsg]);
    setThinking(true);
    let reply = "";
    try {
      const { data } = await axios.post(`${API}/ai/chat`, {
        session_id: sessionRef.current,
        kiosk_id: kiosk?.kiosk_id,
        resident_id: resident?.resident_id,
        message: text,
      }, { timeout: 15000 });
      reply = data.reply || "";
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
      await speak(reply);
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
      // Offline fallback — never let the resident hear silence.
      const fallback = OFFLINE_LINES[offlineCursorRef.current % OFFLINE_LINES.length];
      offlineCursorRef.current += 1;
      reply = fallback;
      setMessages((m) => [...m, { role: "assistant", content: fallback }]);
      await speak(fallback);
    } finally {
      setThinking(false);
    }
    // Claude is doing the semantic understanding — if CAOS's own reply
    // signals "I'll be quiet / I'll rest / just rest", that IS the intent
    // to enter sleep mode. Much more reliable than pattern-matching the
    // resident's free-form speech.
    const replyLower = (reply || "").toLowerCase();
    const SLEEP_REPLY_CUES = [
      "i'll be quiet", "ill be quiet", "i will be quiet",
      "i'll be right here", "ill be right here", "i will be right here",
      "i'll be here if you need", "ill be here if you need",
      "i'll wait quietly", "ill wait quietly",
      "i'll let you rest", "ill let you rest", "i will let you rest",
      "just rest", "rest now", "get some rest",
      "i understand. i'll", "i understand, i'll", "i understand. ill",
      "i'll stop talking", "ill stop talking",
    ];
    if (SLEEP_REPLY_CUES.some((c) => replyLower.includes(c))) {
      sleepingRef.current = true;
      setSleeping(true);
    }
  };

  // Voice recording
  const startRecord = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      const chunks = [];
      rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        if (blob.size < 1500) {
          toast.info("I didn't catch that. Hold the button a bit longer and try again.");
          setRecording(false);
          return;
        }
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
      rec.start(250);
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
      <div className={`min-h-screen bg-caos-ambient text-caos-ink p-8 md:p-12 flex flex-col ${a11yRootClass}`}>
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
              aria-label={`Voice: ${voiceId}. Tap to change.`}
              title="Change voice"
              className="px-3 py-2 rounded-full bg-white border border-caos-line text-caos-forest hover:bg-caos-forest hover:text-white flex items-center gap-1 text-sm font-bold uppercase tracking-wider"
            >
              <Sparkles className="w-4 h-4" /> {voiceId}
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
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute">Welcome</p>
          <h1 className="kiosk-hello mt-6 font-display text-5xl md:text-7xl lg:text-[110px] font-light tracking-tighter leading-[0.95] text-caos-forest">
            {resident ? `Hello, ${resident.name.split(" ")[0]}.` : "Hello."}
          </h1>
          <p className="kiosk-prompt mt-8 text-2xl md:text-3xl text-caos-ink/80 leading-snug">
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

        {/* Voice picker — accessible from a11y row. Not part of the hero
            flow, so residents don't get distracted. Admin/setup use only. */}
        <Dialog open={voicePickerOpen} onOpenChange={setVoicePickerOpen}>
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-display text-2xl text-caos-forest">Choose CAOS's voice</DialogTitle>
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
              Note: "Maple" is only available in the ChatGPT app, not in the OpenAI voice API. The voices above are the closest alternatives.
            </p>
          </DialogContent>
        </Dialog>
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
            {autoVoice ? (
              <div className="w-full rounded-[32px] bg-white border-2 border-caos-line p-6 text-center" data-testid="kiosk-autovoice-indicator">
                {speaking && (
                  <div className="flex flex-col items-center gap-2">
                    <Volume2 className="w-16 h-16 text-caos-terracotta animate-pulse" />
                    <p className="text-2xl font-display font-medium text-caos-forest">CAOS is speaking...</p>
                    <p className="text-sm text-caos-mute uppercase tracking-[0.2em]">please listen</p>
                  </div>
                )}
                {!speaking && recording && (
                  <div className="flex flex-col items-center gap-2">
                    <Mic className="w-16 h-16 text-caos-moss animate-pulse" />
                    <p className="text-2xl font-display font-medium text-caos-forest">Your turn — I'm listening</p>
                    <p className="text-sm text-caos-mute uppercase tracking-[0.2em]">speak naturally</p>
                  </div>
                )}
                {!speaking && !recording && thinking && (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-16 h-16 rounded-full border-4 border-caos-forest border-t-transparent animate-spin" />
                    <p className="text-2xl font-display font-medium text-caos-forest">Thinking...</p>
                  </div>
                )}
                {!speaking && !recording && !thinking && !sleeping && (
                  <div className="flex flex-col items-center gap-2">
                    <Mic className="w-16 h-16 text-caos-mute" />
                    <p className="text-xl font-display font-medium text-caos-mute">Ready</p>
                  </div>
                )}
                {sleeping && (
                  <div className="flex flex-col items-center gap-4 py-4">
                    <div className="w-16 h-16 rounded-full bg-caos-ambient border-2 border-caos-line flex items-center justify-center">
                      <Mic className="w-8 h-8 text-caos-mute" />
                    </div>
                    <p className="text-2xl font-display font-medium text-caos-forest">I'm right here.</p>
                    <p className="text-base text-caos-mute leading-snug text-center max-w-md">
                      Help is still on the way. Tap the button when you'd like me to listen again.
                    </p>
                    <button
                      onClick={wakeFromSleep}
                      data-testid="kiosk-wake-btn"
                      className="mt-2 px-10 py-5 rounded-full bg-caos-forest hover:bg-caos-forest-hover text-white text-xl font-display font-medium shadow-lg transition-all"
                    >
                      <Mic className="w-6 h-6 mr-3 inline" /> Tap to talk again
                    </button>
                  </div>
                )}
              </div>
            ) : (
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
                {recording ? (<><MicOff className="w-10 h-10 mr-4" /> Release to send</>) : (<><Mic className="w-10 h-10 mr-4" /> Hold to talk</>)}
              </Button>
            )}
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
    </div>
  );
}
