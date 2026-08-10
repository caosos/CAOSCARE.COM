/**
 * useRealtimeVoice — full-duplex voice via OpenAI Realtime API + WebRTC.
 *
 * Browser ↔ OpenAI directly stream audio over WebRTC. Backend mints an
 * ephemeral session token and forwards SDP. Audio never touches our server.
 *
 * Tool calling is wired here: when the model emits a `function_call`, this
 * hook dispatches the matching CAOS public endpoint (room temperature,
 * lights, TV, nurse call, mark resting), sends the result back over the
 * data channel as a `function_call_output` item, and asks the model to
 * speak its confirmation. That's the difference between CAOS pretending
 * to turn down the AC and actually doing it.
 *
 * StrictMode-safe: every start() carries a generation token. If a teardown
 * happens mid-flight (StrictMode mount→unmount→remount, or user end-call
 * during connect), we bump the generation and the in-flight start exits
 * cleanly without leaving orphan peer connections — that's what caused the
 * earlier "two voices back-to-back" bug.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "../lib/api";

// Map a model-emitted function name to the CAOS public endpoint that should
// execute it. Returns a short string to read back to the model so it can
// confirm the action verbally. Designed so a missing room or device fails
// gracefully (the model says "I couldn't reach the AC, I'll let the nurse
// know") instead of throwing the whole session.
//
// IMPORTANT: the backend `/devices/.../command` endpoint validates `action`
// against a strict enum (power | brightness | temperature | fan_speed |
// volume | channel | color | position). The AI tools speak in human terms
// (state="on", target_f=72) so this layer translates between them. Mismatch
// = HTTP 422 = silent failure where CAOS promises an action that never ran.
async function postRoomCommand(room, action, value) {
  const r = await fetch(`${API}/devices/public/room/${encodeURIComponent(room)}/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, value }),
  });
  return r;
}

async function executeTool({ name, args, ctx }) {
  const room = ctx?.room;
  const residentId = ctx?.resident_id;
  const kioskId = ctx?.kiosk_id;
  try {
    if (name === "adjust_room_temperature") {
      if (!room) return { ok: false, message: "no room context — I can't reach the climate control here." };
      const targetF = Math.max(60, Math.min(85, Number(args.target_f) || 72));
      const r = await postRoomCommand(room, "temperature", targetF);
      if (!r.ok) return { ok: false, message: `couldn't reach the AC (${r.status}). I'll let the nurse know.` };
      return { ok: true, message: `set the room to ${targetF} degrees.` };
    }
    if (name === "toggle_light") {
      if (!room) return { ok: false, message: "no room context — I can't reach the lights here." };
      // Power first; if a specific brightness was requested AND state="on",
      // follow with a brightness command so dimmable bulbs land at the right level.
      const r = await postRoomCommand(room, "power", args.state);
      if (!r.ok) return { ok: false, message: `couldn't reach the light (${r.status}).` };
      if (args.state === "on" && typeof args.brightness === "number") {
        await postRoomCommand(room, "brightness", Math.max(0, Math.min(100, args.brightness)));
      }
      return { ok: true, message: `turned the light ${args.state}.` };
    }
    if (name === "toggle_tv") {
      if (!room) return { ok: false, message: "no room context — I can't reach the TV here." };
      const r = await postRoomCommand(room, "power", args.state);
      if (!r.ok) return { ok: false, message: `couldn't reach the TV (${r.status}).` };
      if (args.state === "on" && typeof args.volume === "number") {
        await postRoomCommand(room, "volume", Math.max(0, Math.min(100, args.volume)));
      }
      return { ok: true, message: `turned the TV ${args.state}${args.state === "on" && typeof args.volume === "number" ? ` at volume ${args.volume}` : ""}.` };
    }
    if (name === "call_for_help") {
      const r = await fetch(`${API}/alerts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kiosk_id: kioskId || null,
          resident_id: residentId || null,
          severity: args.severity === "emergency" ? "emergency" : "assist",
          message: args.reason || "AI-initiated call for help during conversation",
          triggered_by: "ai_triage",
        }),
      });
      if (!r.ok) return { ok: false, message: `I tried to call a nurse but the call didn't go through (${r.status}). Please press the red button.` };
      return { ok: true, message: "a nurse has been paged. I'm right here with you." };
    }
    if (name === "request_staff_help") {
      const r = await fetch(`${API}/tasks/resident-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: args.category,
          resident_id: residentId || null,
          room: room || null,
          resident_words: args.summary || null,
          summary: args.summary || "Resident request",
          priority: args.priority || "normal",
          source: "aria_voice",
          conversation_session_id: sessionIdRef.current,
        }),
      });
      if (!r.ok) return { ok: false, message: `couldn't send that request (${r.status}) - please try the call button instead.` };
      const data = await r.json();
      return { ok: true, message: `request created (${data.status}) and sent to ${args.category}.`, task_id: data.task_id };
    }
    if (name === "check_request_status") {
      const qs = new URLSearchParams();
      if (residentId) qs.set("resident_id", residentId);
      else if (room) qs.set("room", room);
      else qs.set("conversation_session_id", sessionIdRef.current);
      if (args.category) qs.set("category", args.category);
      const r = await fetch(`${API}/tasks/resident-request/status?${qs.toString()}`);
      if (!r.ok) return { ok: false, message: `couldn't check that (${r.status}).` };
      const data = await r.json();
      if (!data.found) return { ok: true, message: "no matching request found on record." };
      return {
        ok: true,
        message: `status: ${data.status}${data.acknowledged ? " (acknowledged)" : " (not yet acknowledged)"}${data.assigned_to_name ? `, assigned to ${data.assigned_to_name}` : ""}.`,
      };
    }
    if (name === "mark_resting") {
      // No backend side-effect; the function existing tells the model to fall
      // silent. We surface a session-level flag so the UI can dim the orb.
      return { ok: true, message: "going quiet now. I'll be right here when you need me." };
    }
    if (name === "get_current_time") {
      // The backend already injected the facility's current time into the
      // session prompt at session start, but for long calls (or just for a
      // fresh value) we re-fetch via the weather endpoint's sibling — no
      // separate route needed: include it in /research is overkill. Hit the
      // same /weather/current call which carries the facility timezone, and
      // return a clean spoken summary built client-side from Date.now() in
      // the facility tz the backend told us about.
      const tz = ctx?.facility_tz || "America/New_York";
      const label = ctx?.facility_label || "the facility";
      try {
        const d = new Date();
        const fmt = new Intl.DateTimeFormat("en-US", {
          timeZone: tz,
          weekday: "long", month: "long", day: "numeric", year: "numeric",
          hour: "numeric", minute: "2-digit",
        });
        return { ok: true, message: `it's ${fmt.format(d)} at ${label}.` };
      } catch {
        return { ok: true, message: `it's ${new Date().toLocaleString()}.` };
      }
    }
    if (name === "get_weather") {
      const qs = args.location ? `?label=${encodeURIComponent(args.location)}` : "";
      const r = await fetch(`${API}/weather/current${qs}`);
      if (!r.ok) return { ok: false, message: `couldn't reach the weather service (${r.status}).` };
      const w = await r.json();
      // Re-tell rather than dump. The model is instructed to read this naturally.
      return { ok: true, message: w.narrative || `${w.temperature_f}° and ${w.condition}.` };
    }
    if (name === "research_topic") {
      const r = await fetch(`${API}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: args.question || "" }),
      });
      if (!r.ok) return { ok: false, message: `couldn't reach the research service (${r.status}).` };
      const j = await r.json();
      return {
        ok: true,
        message: j.answer || "I didn't find anything useful on that.",
        source: j.source,
        citations: j.citations || [],
      };
    }
    if (name === "set_timer") {
      const minutes = Math.max(0.1, Math.min(720, Number(args.minutes) || 5));
      const label = (args.label || "your reminder").toString().slice(0, 200);
      const r = await fetch(`${API}/timers/public`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          minutes,
          label,
          resident_id: residentId || null,
          room: room || null,
          kiosk_id: kioskId || null,
        }),
      });
      if (!r.ok) return { ok: false, message: `couldn't set the timer (${r.status}).` };
      return { ok: true, message: `okay, I'll remind you in ${minutes < 1 ? `${Math.round(minutes * 60)} seconds` : `${minutes} minutes`}.` };
    }
    if (name === "update_preferred_name") {
      const newName = (args.preferred_name || "").toString().trim().slice(0, 60);
      if (!newName) return { ok: false, message: "I didn't catch the name." };
      if (!residentId) return { ok: true, message: `okay, I'll call you ${newName} from now on.` };
      const r = await fetch(`${API}/residents/${residentId}/preferred-name`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferred_name: newName }),
      });
      if (!r.ok) return { ok: false, message: `I'll call you ${newName} from now on (didn't quite save it though).` };
      return { ok: true, message: `okay, ${newName} it is. Saved.` };
    }
    if (name === "end_call") {
      // The actual hang-up happens in the calling layer (handleFunctionCall)
      // because we need access to the peer connection. Returning here just
      // gives the model its short verbal goodbye to speak.
      return { ok: true, message: "goodbye for now. I'm right here when you call." };
    }
    if (name === "end_conversation") {
      // Aria's own equivalent of end_call - same "actual teardown happens
      // in handleFunctionCall" pattern, just a different name so her
      // instructions don't have to reuse resident-call language.
      return { ok: true, message: "sounds good, talk soon." };
    }
    return { ok: false, message: `tool ${name} is not wired yet.` };
  } catch (e) {
    return { ok: false, message: `tool error: ${e?.message || "unknown"}.` };
  }
}

export function useRealtimeVoice({
  voice = "shimmer", residentId, kioskId, room, onEndCall,
  sessionEndpoint = "/realtime/session", sessionPayload,
} = {}) {
  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const audioElRef = useRef(null);
  const localStreamRef = useRef(null);
  const startGenRef = useRef(0);            // bumps on every stop() — invalidates in-flight starts
  const ctxRef = useRef({ resident_id: residentId, kiosk_id: kioskId, room });
  const pendingUserRef = useRef("");        // user transcript awaiting its assistant pair
  const sessionIdRef = useRef(`rt_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [resting, setResting] = useState(false);

  // Keep tool-call context fresh if the parent passes new props mid-call
  useEffect(() => {
    ctxRef.current = { resident_id: residentId, kiosk_id: kioskId, room };
  }, [residentId, kioskId, room]);

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
    setResting(false);
  }, []);

  useEffect(() => () => stop(), [stop]);

  const start = useCallback(async () => {
    if (pcRef.current) return;              // already connected
    const myGen = ++startGenRef.current;
    sessionIdRef.current = `rt_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`;
    pendingUserRef.current = "";

    setError(null);
    setStatus("connecting");
    let pc = null;
    let stream = null;
    try {
      // 1. Mint ephemeral session
      const sessionRes = await fetch(`${API}${sessionEndpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          sessionPayload || {
            voice,
            resident_id: residentId || null,
            kiosk_id: kioskId || null,
            room: room || null,
          }
        ),
      });
      if (myGen !== startGenRef.current) return;   // canceled
      if (!sessionRes.ok) throw new Error(`session ${sessionRes.status}`);
      const session = await sessionRes.json();
      if (myGen !== startGenRef.current) return;
      // /realtime/client_secrets (the endpoint the backend calls) returns the
      // ephemeral key as a top-level `value`, not nested under `client_secret`
      // — that older shape belongs to the legacy /realtime/sessions endpoint.
      const ephemeral = session?.value || session?.client_secret?.value;
      if (!ephemeral) throw new Error("no ephemeral key");
      const caos = session._caos || {};
      // Backend authority on context — overrides whatever the parent passed
      if (caos.context) ctxRef.current = { ...ctxRef.current, ...caos.context };

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

      // 4. Data channel — events, transcripts, session.update, tool dispatch
      const dc = pc.createDataChannel("oai-events");

      // Helper: send a JSON event safely
      const send = (obj) => {
        try { dc.send(JSON.stringify(obj)); } catch {}
      };

      // Helper: dispatch a tool call coming from the model
      const handleFunctionCall = async (fn) => {
        let parsed = {};
        try { parsed = fn.arguments ? JSON.parse(fn.arguments) : {}; } catch {}
        const result = await executeTool({ name: fn.name, args: parsed, ctx: ctxRef.current });
        if (myGen !== startGenRef.current) return;
        // Tell the model what happened. The output goes onto the conversation
        // as a `function_call_output` item, then we ask the model to respond.
        send({
          type: "conversation.item.create",
          item: {
            type: "function_call_output",
            call_id: fn.call_id,
            output: JSON.stringify(result),
          },
        });
        if (fn.name === "mark_resting") {
          // Resident asked us to be quiet. Don't trigger a new spoken response;
          // the model will stay silent until VAD detects fresh speech.
          setResting(true);
        } else if (fn.name === "end_call" || fn.name === "end_conversation") {
          // Resident/Michael asked to wrap up. Let the model speak its
          // goodbye, then tear the connection down ~2.5s later (long enough
          // for the farewell line to play out, short enough not to feel
          // awkward). Same teardown for both - just two tool names so each
          // persona's instructions can use natural language for its context.
          send({ type: "response.create" });
          setTimeout(() => {
            try { stop(); } catch {}
            try { onEndCall?.(); } catch {}
          }, 2500);
        } else {
          // Ask the model to speak its short confirmation, drawing on the tool result.
          send({ type: "response.create" });
        }
      };

      dc.onopen = () => {
        if (myGen !== startGenRef.current) return;
        // FAIL CLOSED: the authoritative persona instructions come from the
        // backend (_caos.instructions). If they're missing, do NOT fall back
        // to a generic unidentified model talking to a resident - refuse to
        // start instead. Wrong-but-talking is worse than unavailable here.
        if (!caos.instructions) {
          setError("Aria configuration could not be loaded.");
          setStatus("error");
          try { stop(); } catch {}
          return;
        }
        // Apply the full session config from the backend: instructions, tools,
        // VAD timing, temperature. session.update is the canonical way to
        // configure a Realtime session post-mint.
        const update = {
          type: "session.update",
          session: {
            instructions: caos.instructions,
            voice: caos.voice || voice,
            modalities: ["audio", "text"],
            input_audio_transcription: { model: "whisper-1", language: "en" },
          },
        };
        if (caos.tools) update.session.tools = caos.tools;
        if (caos.tool_choice) update.session.tool_choice = caos.tool_choice;
        if (caos.turn_detection) update.session.turn_detection = caos.turn_detection;
        if (typeof caos.temperature === "number") update.session.temperature = caos.temperature;
        send(update);
        setStatus("live");
      };

      dc.onmessage = (ev) => {
        if (myGen !== startGenRef.current) return;
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }

        if (msg.type === "input_audio_buffer.speech_started") {
          setStatus("listening");
          setResting(false);   // resident spoke again → wake from rest
        }
        if (msg.type === "input_audio_buffer.speech_stopped") setStatus("live");
        if (msg.type === "response.audio.delta") setStatus("speaking");
        if (msg.type === "response.done") setStatus("live");
        if (msg.type === "conversation.item.input_audio_transcription.completed") {
          const userText = msg.transcript || "";
          setTranscript((t) => [...t, { role: "user", text: userText, ts: Date.now() }]);
          // Stash the user side of the turn so we can pair it with the
          // assistant reply once that arrives, then ship it to the memory
          // extractor. This is the single change that lets Realtime voice
          // sessions actually grow CAOS's memory of the resident over time.
          pendingUserRef.current = userText;
        }
        if (msg.type === "response.audio_transcript.done") {
          const aiText = msg.transcript || "";
          setTranscript((t) => [...t, { role: "assistant", text: aiText, ts: Date.now() }]);
          const userText = pendingUserRef.current;
          pendingUserRef.current = "";
          const rid = ctxRef.current?.resident_id;
          const ownerId = ctxRef.current?.owner_user_id;
          if (rid && (userText || aiText)) {
            // Fire-and-forget; never block the voice loop on this.
            fetch(`${API}/memory/realtime-turn`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                resident_id: rid,
                session_id: sessionIdRef.current,
                user_text: userText,
                assistant_text: aiText,
              }),
            }).catch(() => {});
          } else if (ownerId && (userText || aiText)) {
            // Aria's own (operator) sessions - same fire-and-forget pattern,
            // verbatim turn record so every conversation has a real thread,
            // not just a post-hoc summary.
            const postTurn = (role, content) => {
              if (!content) return;
              fetch(`${API}/aria/conversation-turn`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  owner_user_id: ownerId,
                  session_id: sessionIdRef.current,
                  role,
                  content,
                }),
              }).catch(() => {});
            };
            postTurn("user", userText);
            postTurn("assistant", aiText);
          }
        }
        // Tool call dispatch — the OpenAI Realtime API streams arguments and
        // emits a single `done` event when the call is fully assembled.
        if (msg.type === "response.function_call_arguments.done") {
          handleFunctionCall({
            call_id: msg.call_id,
            name: msg.name,
            arguments: msg.arguments,
          });
        }
        if (msg.type === "error") setError(msg.error?.message || "Realtime error");
      };

      // 5. SDP exchange (offer → backend → OpenAI → answer)
      // FIXED 2026-08-09 (real bug): this used to negotiate without the
      // ephemeral key at all, so the backend authenticated with its own
      // server key and built a brand-new, generic, instructions-less
      // session - the actual live call never used the Aria/companion
      // instructions minted in step 1. Now forwards the same ephemeral
      // key so the call continues THAT already-configured session.
      // Empirically verified against OpenAI directly (real SDP via
      // aiortc + this exact key -> HTTP 201 with a valid answer) before
      // wiring it in here.
      const offer = await pc.createOffer();
      if (myGen !== startGenRef.current) throw new Error("canceled");
      await pc.setLocalDescription(offer);
      const negRes = await fetch(`${API}/realtime/negotiate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/sdp",
          "X-CAOS-Ephemeral-Key": ephemeral,
        },
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
  }, [voice, residentId, kioskId, room, sessionEndpoint, sessionPayload]);

  return { status, error, transcript, resting, start, stop, audioElRef };
}
