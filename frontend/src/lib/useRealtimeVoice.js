/**
 * useRealtimeVoice — full-duplex voice via OpenAI Realtime API + WebRTC.
 *
 * Browser ↔ OpenAI directly stream audio over WebRTC. Backend mints an
 * ephemeral session token and forwards SDP. Audio never touches our server.
 *
 * StrictMode-safe: every start() carries a generation token. If a teardown
 * happens mid-flight (StrictMode mount→unmount→remount, or user end-call
 * during connect), we bump the generation and the in-flight start exits
 * cleanly without leaving orphan peer connections — that's what caused the
 * earlier "two voices back-to-back" bug.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "../lib/api";

export function useRealtimeVoice({ voice = "shimmer", residentId } = {}) {
  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const audioElRef = useRef(null);
  const localStreamRef = useRef(null);
  const startGenRef = useRef(0);            // bumps on every stop() — invalidates in-flight starts
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [transcript, setTranscript] = useState([]);

  const stop = useCallback(() => {
    startGenRef.current += 1;               // cancel any pending start()
    try { dcRef.current?.close(); } catch {}
    try { pcRef.current?.getSenders().forEach((s) => s.track && s.track.stop()); } catch {}
    try { pcRef.current?.close(); } catch {}
    try { localStreamRef.current?.getTracks().forEach((t) => t.stop()); } catch {}
    try { if (audioElRef.current) audioElRef.current.srcObject = null; } catch {}
    pcRef.current = null;
    dcRef.current = null;
    localStreamRef.current = null;
    setStatus("idle");
  }, []);

  useEffect(() => () => stop(), [stop]);

  const start = useCallback(async () => {
    if (pcRef.current) return;              // already connected
    const myGen = ++startGenRef.current;
    const alive = () => myGen === startGenRef.current && pcRef.current !== null || myGen === startGenRef.current;

    setError(null);
    setStatus("connecting");
    let pc = null;
    let stream = null;
    try {
      // 1. Mint ephemeral session
      const sessionRes = await fetch(`${API}/realtime/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice, resident_id: residentId || null }),
      });
      if (myGen !== startGenRef.current) return;   // canceled
      if (!sessionRes.ok) throw new Error(`session ${sessionRes.status}`);
      const session = await sessionRes.json();
      if (myGen !== startGenRef.current) return;
      const ephemeral = session?.client_secret?.value;
      if (!ephemeral) throw new Error("no ephemeral key");
      const caos = session._caos || {};

      // 2. Mic capture (full-duplex: track stays live for the whole session)
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      if (myGen !== startGenRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      // 3. Peer connection. Only commit refs once we know we're not canceled.
      pc = new RTCPeerConnection();
      pc.ontrack = (ev) => {
        const el = audioElRef.current;
        if (el) el.srcObject = ev.streams[0];
      };
      stream.getTracks().forEach((t) => pc.addTrack(t, stream));

      // 4. Data channel — events, transcripts, session.update
      const dc = pc.createDataChannel("oai-events");
      dc.onopen = () => {
        if (myGen !== startGenRef.current) return;
        try {
          dc.send(JSON.stringify({
            type: "session.update",
            session: {
              instructions: caos.instructions || "You are CAOS, a calm companion.",
              voice: caos.voice || voice,
              modalities: ["audio", "text"],
              input_audio_transcription: { model: "whisper-1" },
            },
          }));
        } catch {}
        setStatus("live");
      };
      dc.onmessage = (ev) => {
        if (myGen !== startGenRef.current) return;
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "input_audio_buffer.speech_started") setStatus("listening");
          if (msg.type === "input_audio_buffer.speech_stopped") setStatus("live");
          if (msg.type === "response.audio.delta") setStatus("speaking");
          if (msg.type === "response.done") setStatus("live");
          if (msg.type === "conversation.item.input_audio_transcription.completed") {
            setTranscript((t) => [...t, { role: "user", text: msg.transcript || "", ts: Date.now() }]);
          }
          if (msg.type === "response.audio_transcript.done") {
            setTranscript((t) => [...t, { role: "assistant", text: msg.transcript || "", ts: Date.now() }]);
          }
          if (msg.type === "error") setError(msg.error?.message || "Realtime error");
        } catch { /* ignore non-JSON */ }
      };

      // 5. SDP exchange (offer → backend → OpenAI → answer)
      const offer = await pc.createOffer();
      if (myGen !== startGenRef.current) throw new Error("canceled");
      await pc.setLocalDescription(offer);
      const negRes = await fetch(`${API}/realtime/negotiate`, {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: offer.sdp,
      });
      if (myGen !== startGenRef.current) throw new Error("canceled");
      if (!negRes.ok) throw new Error(`negotiate ${negRes.status}`);
      const { sdp: answerSdp } = await negRes.json();
      if (myGen !== startGenRef.current) throw new Error("canceled");
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

      // Commit only after success — partial state never sticks
      pcRef.current = pc;
      dcRef.current = dc;
      localStreamRef.current = stream;
    } catch (e) {
      // Fully tear down anything we built before the failure
      try { pc?.close(); } catch {}
      try { stream?.getTracks().forEach((t) => t.stop()); } catch {}
      if (myGen === startGenRef.current && e?.message !== "canceled") {
        setError(e?.message || "Failed to start voice");
        setStatus("error");
      }
    }
    // suppress unused eslint warning for the alive helper that documents intent
    void alive;
  }, [voice, residentId]);

  return { status, error, transcript, start, stop, audioElRef };
}
