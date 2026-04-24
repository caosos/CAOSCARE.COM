/**
 * useRealtimeVoice — full-duplex voice via OpenAI Realtime API + WebRTC.
 *
 * Browser ↔ OpenAI directly stream audio over WebRTC. Our backend mints
 * an ephemeral session token (so the OpenAI key never ships to the browser)
 * and forwards the SDP offer/answer. After that, audio is peer-to-peer.
 *
 * Late chime-ins are handled natively by the OpenAI Realtime API: as long
 * as the mic track stays live and server-side VAD is on (default), the
 * input audio buffer keeps appending and the model replies when you stop
 * talking. No custom turn detection on our side.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "../lib/api";

export function useRealtimeVoice({ voice = "shimmer", residentId } = {}) {
  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const audioElRef = useRef(null);
  const localStreamRef = useRef(null);
  const [status, setStatus] = useState("idle"); // idle | connecting | live | speaking | listening | error
  const [error, setError] = useState(null);
  const [transcript, setTranscript] = useState([]); // [{role, text, ts}]

  const stop = useCallback(() => {
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
    if (pcRef.current) return;
    setError(null);
    setStatus("connecting");
    try {
      // 1. Mint ephemeral session
      const sessionRes = await fetch(`${API}/realtime/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice, resident_id: residentId || null }),
      });
      if (!sessionRes.ok) throw new Error(`session ${sessionRes.status}`);
      const session = await sessionRes.json();
      const ephemeral = session?.client_secret?.value;
      if (!ephemeral) throw new Error("no ephemeral key");
      const caos = session._caos || {};

      // 2. WebRTC peer connection
      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      // 3. Remote audio sink
      let audioEl = audioElRef.current;
      if (!audioEl) {
        audioEl = document.createElement("audio");
        audioEl.autoplay = true;
        audioElRef.current = audioEl;
      }
      pc.ontrack = (ev) => { audioEl.srcObject = ev.streams[0]; };

      // 4. Local mic — full-duplex: track stays live for the entire session
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      localStreamRef.current = stream;
      stream.getTracks().forEach((t) => pc.addTrack(t, stream));

      // 5. Data channel for events (transcripts, session.update, etc.)
      const dc = pc.createDataChannel("oai-events");
      dcRef.current = dc;
      dc.onopen = () => {
        // Inject CAOS Care system prompt + voice on connect.
        // Server-side VAD is default ON, which gives us natural turn-taking
        // and append-mode chime-ins out of the box.
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

      // 6. SDP exchange (offer → backend → OpenAI → answer)
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      const negRes = await fetch(`${API}/realtime/negotiate`, {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: offer.sdp,
      });
      if (!negRes.ok) throw new Error(`negotiate ${negRes.status}`);
      const { sdp: answerSdp } = await negRes.json();
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
    } catch (e) {
      setError(e?.message || "Failed to start voice");
      setStatus("error");
      stop();
    }
  }, [voice, residentId, stop]);

  return { status, error, transcript, start, stop };
}
