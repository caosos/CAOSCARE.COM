/**
 * Low-cost voice transport (docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md). Stands where the WebRTC peer connection
 * and its "oai-events" data channel stand in realtimeConnection.js, and produces the same Realtime events the
 * handler (realtimeMessageHandler.js) already understands - so Aria's tools, grounding, memory and receipts
 * are unchanged. Behind it: local turn detection (room-node/aria_voice, ws://127.0.0.1:8794) and the backend's
 * receipted speech-to-text, text model and voice (routes/aria_voice.py). No Realtime model is used.
 * Chosen per kiosk (useVoiceTransport.js); the voice is the one chosen in the kiosk's voice picker.
 */
import { GOODBYE_INSTRUCTIONS, GOODBYE_LINE } from "./endController";

export const VOICE_SERVICE_URL = "ws://127.0.0.1:8794";
const SENTENCE_END = /[.!?…]["')\]]?\s+/;
const FIRST_CLAUSE = /^.{24,}?[,;:—]\s+/;   // a reply's opening clause is spoken without waiting for its full stop

/** Realtime conversation items -> chat messages (what the backend's text model takes). */
export function chatMessage(item) {
  if (item?.type === "function_call_output") return { role: "tool", tool_call_id: item.call_id, content: String(item.output ?? "") };
  if (item?.type === "message" && (item.role === "user" || item.role === "assistant")) {
    const text = (item.content || []).map((c) => c.text || c.transcript || "").join(" ").trim();
    return text ? { role: item.role, content: text } : null;
  }
  return null;
}

/** The conversation as the chat API accepts it: a tool call goes with its result. Realtime lets a reply be asked for
 * while a call is still unanswered (e.g. end_call during the goodbye); here such a call - and a result whose call
 * is not in the conversation - is left out of that request, never invented. */
export function requestItems(items) {
  const answered = new Set(items.filter((m) => m.role === "tool").map((m) => m.tool_call_id));
  const asked = new Set();
  const out = [];
  for (const m of items) {
    if (m.role === "assistant" && m.tool_calls) {
      const calls = m.tool_calls.filter((c) => answered.has(c.id));
      calls.forEach((c) => asked.add(c.id));
      if (calls.length) out.push({ ...m, tool_calls: calls });
      else if (m.content) out.push({ role: "assistant", content: m.content });
    } else if (m.role === "tool") {
      if (asked.has(m.tool_call_id)) out.push(m);
    } else out.push(m);
  }
  return out;
}

/** Splits streamed text into finished sentences; returns [sentences, remainder]. */
export function takeSentences(buf, first = false) {
  const out = [];
  let m;
  if (first && !SENTENCE_END.test(buf) && (m = FIRST_CLAUSE.exec(buf))) {
    out.push(m[0].trim());
    buf = buf.slice(m[0].length);
  }
  while ((m = SENTENCE_END.exec(buf))) {
    out.push(buf.slice(0, m.index + m[0].length).trim());
    buf = buf.slice(m.index + m[0].length);
  }
  return [out, buf];
}

/** Chrome's echo canceller only subtracts audio it plays for WebRTC. Aria's voice is therefore sent through a local
 * loopback peer connection into the page's audio element (as the Realtime call audio is), so the microphone's AEC
 * removes her own voice and it never reads as the resident barging in (Room 214, 2026-10-17 rt_hyovgwag). */
async function echoCancelledOutput(ctx, audioEl, RTC) {
  const dest = ctx.createMediaStreamDestination();
  const a = new RTC(), b = new RTC();
  a.onicecandidate = (e) => e.candidate && b.addIceCandidate(e.candidate).catch(() => {});
  b.onicecandidate = (e) => e.candidate && a.addIceCandidate(e.candidate).catch(() => {});
  b.ontrack = (e) => { audioEl.srcObject = e.streams[0]; audioEl.play?.().catch(() => {}); };
  dest.stream.getTracks().forEach((t) => a.addTrack(t, dest.stream));
  await a.setLocalDescription(await a.createOffer());
  await b.setRemoteDescription(a.localDescription);
  await b.setLocalDescription(await b.createAnswer());
  await a.setRemoteDescription(b.localDescription);
  return { node: dest, close: () => { try { a.close(); b.close(); audioEl.srcObject = null; } catch {} } };
}

/** Plays PCM16 chunks back to back; stop() cuts playback at once. With an audio element and WebRTC available, the
 * sound goes through the echo-cancelled path above; otherwise straight to the speakers. */
export function createPlayer({ AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext),
  audioEl = null, RTC = typeof window !== "undefined" && window.RTCPeerConnection } = {}) {
  let ctx = null, out = null, next = 0, live = [], onIdle = null;
  const ready = () => {
    if (!ctx) {
      ctx = new AudioCtx();
      out = audioEl && RTC ? echoCancelledOutput(ctx, audioEl, RTC).catch(() => null) : Promise.resolve(null);
    }
    return out;
  };
  return {
    set onIdle(fn) { onIdle = fn; },
    get playing() { return live.length > 0; },
    prepare() { return ready(); },
    play(pcm16, rate) {
      ready();
      const f = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) f[i] = pcm16[i] / 32768;
      const buf = ctx.createBuffer(1, f.length, rate);
      buf.copyToChannel(f, 0);
      const src = ctx.createBufferSource();
      src.buffer = buf;
      out.then((sink) => src.connect(sink ? sink.node : ctx.destination));
      next = Math.max(next, ctx.currentTime + 0.05);
      src.start(next); next += buf.duration;
      live.push(src);
      src.onended = () => { live = live.filter((s) => s !== src); if (!live.length) onIdle?.(); };
    },
    stop() { const was = live.length > 0; live.forEach((s) => { try { s.onended = null; s.stop(); } catch {} }); live = []; next = 0; return was; },
    close() { this.stop(); out?.then((sink) => sink?.close()); try { ctx?.close(); } catch {} },
  };
}

/** Streams the page's (echo-cancelled) microphone to the voice service as PCM16 16 kHz. */
function startMic(stream, ws, AudioCtx) {
  const ctx = new AudioCtx({ sampleRate: 16000 });
  const src = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(2048, 1, 1);
  proc.onaudioprocess = (e) => {
    if (ws.readyState !== 1) return;
    const f = e.inputBuffer.getChannelData(0), out = new Int16Array(f.length);
    for (let i = 0; i < f.length; i++) out[i] = Math.max(-1, Math.min(1, f[i])) * 32767;
    ws.send(out.buffer);
  };
  src.connect(proc); proc.connect(ctx.destination);
  return () => { try { proc.disconnect(); src.disconnect(); ctx.close(); } catch {} };
}

function joinBytes(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0); out.set(b, a.length);
  return out;
}

export function createCascadeConnection({ session, caos, stream, api, audioEl = null, wsUrl = VOICE_SERVICE_URL,
  WebSocketImpl = WebSocket, fetchImpl = (...a) => fetch(...a), player = createPlayer({ audioEl }),
  AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext) }) {
  const headers = { "X-Aria-Voice-Token": session.token };
  const rate = session.audio_sample_rate || 24000;
  const items = [];                         // the conversation, as chat messages
  let n = 0, autoRespond = true, resp = null, stopMic = null, closed = false;
  const id = (p) => `${p}_${Date.now().toString(36)}_${++n}`;
  const dc = { readyState: "connecting", onopen: null, onmessage: null, onclose: null, send: (s) => onClient(JSON.parse(s)), close };
  const emit = (obj) => { if (!closed) setTimeout(() => dc.onmessage?.({ data: JSON.stringify(obj) }), 0); };
  const ws = new WebSocketImpl(wsUrl);
  player.onIdle = () => {                   // the player also runs dry between sentences: only the reply's end counts
    const r = resp;
    if (r?.speaking && r.done && !r.queue.length && !r.pump) { finishAudio(r); resp = null; }
  };

  function finishAudio(r) { r.speaking = false; emit({ type: "output_audio_buffer.stopped", response_id: r.id }); }
  const wake = (o, k) => { const w = o[k]; o[k] = null; w?.(); };

  // Every finished sentence is requested at once; sentences play strictly in order as their audio streams in.
  function say(r, text, fixed = false) {
    if (!text) return;
    const e = { text, chunks: [], ended: false, wake: null };
    r.queue.push(e); r.said += 1;
    fetchImpl(`${api}/aria-voice/speak`, { method: "POST", signal: r.abort.signal,
      headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ text, fixed }) })
      .then(async (res) => {
        if (!res.ok || !res.body) return;
        const reader = res.body.getReader();
        let carry = null;
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          let bytes = carry ? joinBytes(carry, value) : value;
          carry = null;
          if (bytes.length % 2) { carry = bytes.slice(-1); bytes = bytes.slice(0, -1); }
          if (bytes.length) { e.chunks.push(new Int16Array(bytes.slice().buffer)); wake(e, "wake"); }
        }
      })
      .catch(() => {})
      .finally(() => { e.ended = true; wake(e, "wake"); });
    if (r.pump) wake(r, "wakePump"); else r.pump = pump(r);
  }

  async function pump(r) {
    while (resp === r) {
      const e = r.queue[0];
      if (!e) { if (r.done) break; await new Promise((ok) => { r.wakePump = ok; }); continue; }
      while (resp === r) {
        if (e.chunks.length) {
          if (!r.speaking) { r.speaking = true; emit({ type: "output_audio_buffer.started", response_id: r.id }); }
          if (!e.heard) { e.heard = true; r.heard.push(e.text); }   // reached the speaker
          player.play(e.chunks.shift(), rate);
          continue;
        }
        if (e.ended) break;
        await new Promise((ok) => { e.wake = ok; });
      }
      r.queue.shift();
    }
    r.pump = null;
    if (resp === r && r.done && !player.playing) { if (r.speaking) finishAudio(r); resp = null; }
  }

  function cancel(reason) {
    const r = resp;
    if (!r) return false;
    resp = null; r.abort.abort();
    wake(r, "wakePump"); r.queue.forEach((e) => wake(e, "wake"));
    const wasPlaying = player.stop();
    if (wasPlaying || r.speaking) emit({ type: "output_audio_buffer.cleared", response_id: r.id });
    // Only what reached the speaker counts as said; the unheard rest of the reply is not in the conversation.
    const heard = r.heard.join(" ").trim();
    if (!r.done) {
      if (heard) {
        items.push({ role: "assistant", content: heard });
        emit({ type: "response.output_audio_transcript.done", response_id: r.id, item_id: r.item, transcript: heard });
      }
      emit({ type: "response.done", response: { id: r.id, status: "cancelled", status_details: { reason }, usage: null } });
    } else if (r.itemIndex != null) {
      const it = items[r.itemIndex];
      if (it.tool_calls) it.content = heard || null;
      else if (heard) it.content = heard;
      else items.splice(r.itemIndex, 1);
    }
    return true;
  }

  async function respond(opts = {}) {
    if (resp && !resp.done) return emit({ type: "error", error: { message: "Conversation already has an active response." } });
    if (resp) cancel("superseded");         // a finished reply still playing gives way to the next one
    const r = resp = { id: id("resp"), item: id("item"), queue: [], heard: [], said: 0, text: "", buf: "", calls: [],
      done: false, speaking: false, pump: null, wakePump: null, itemIndex: null, abort: new AbortController() };
    emit({ type: "response.created", response: { id: r.id } });
    const delta = (d) => { r.text += d; emit({ type: "response.output_audio_transcript.delta", response_id: r.id, item_id: r.item, delta: d });
      const [done, rest] = takeSentences(r.buf + d, r.said === 0); r.buf = rest; done.forEach((s) => say(r, s)); };
    // The greeting and the routine goodbye are fixed lines: spoken (and cached) with no reasoning call.
    const fixed = opts.instructions && (opts.instructions === caos.greeting?.instructions ? caos.greeting_line
      : opts.instructions === GOODBYE_INSTRUCTIONS ? GOODBYE_LINE : null);
    try {
      if (fixed) { r.text = fixed; emit({ type: "response.output_audio_transcript.delta", response_id: r.id, item_id: r.item, delta: fixed }); say(r, fixed, true); }
      else await streamReply(r, opts, delta);
    } catch (e) {
      if (r.abort.signal.aborted) return;
      emit({ type: "error", error: { message: `Low-cost voice: ${e.message}` } });
    }
    if (resp !== r) return;                 // cancelled meanwhile
    say(r, r.buf.trim()); r.buf = "";
    const text = r.text.trim();
    if (text || r.calls.length) {
      r.itemIndex = items.length;
      items.push({ role: "assistant", content: text || null,
        ...(r.calls.length ? { tool_calls: r.calls.map((c) => ({ id: c.id, type: "function", function: { name: c.name, arguments: c.arguments } })) } : {}) });
    }
    if (text) emit({ type: "response.output_audio_transcript.done", response_id: r.id, item_id: r.item, transcript: text });
    r.calls.forEach((c) => emit({ type: "response.function_call_arguments.done", response_id: r.id, call_id: c.id, name: c.name, arguments: c.arguments }));
    r.done = true;
    emit({ type: "response.done", response: { id: r.id, status: "completed", usage: null } });
    if (r.pump) wake(r, "wakePump"); else if (!player.playing) resp = null;
  }

  async function streamReply(r, opts, delta) {
    const res = await fetchImpl(`${api}/aria-voice/respond`, { method: "POST", signal: r.abort.signal,
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ items: requestItems(items), ...(opts.instructions ? { instructions: opts.instructions } : {}),
        ...(opts.tool_choice ? { tool_choice: opts.tool_choice } : {}) }) });
    if (!res.ok) throw new Error(`respond ${res.status}`);
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i); buf = buf.slice(i + 2);
        if (!line.startsWith("data: ")) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.type === "text") delta(ev.delta);
        else if (ev.type === "tool_call") r.calls.push(ev);
        else if (ev.type === "error") throw new Error(`provider ${ev.status}`);
      }
    }
  }

  let early = null;                         // transcription started at the speaker's first pause (speech_paused)
  function transcribe(wavB64) {
    const bytes = Uint8Array.from(atob(wavB64), (c) => c.charCodeAt(0));
    return fetchImpl(`${api}/aria-voice/transcribe`, { method: "POST", headers: { ...headers, "Content-Type": "audio/wav" }, body: bytes })
      .then((res) => (res.ok ? res.json() : {})).then((j) => j.text || "").catch(() => "");
  }

  async function heard(wavB64) {
    const item = id("item");
    emit({ type: "input_audio_buffer.speech_stopped", item_id: item });
    const pending = early; early = null;    // still valid only if the speaker did not carry on after the pause
    const text = await (pending || transcribe(wavB64));
    if (closed) return;
    if (text) items.push({ role: "user", content: text });
    emit({ type: "conversation.item.input_audio_transcription.completed", item_id: item, transcript: text });
    if (text && autoRespond) respond();
  }

  function onService(ev) {
    const m = JSON.parse(ev.data);
    if (m.type === "ready") {
      const td = caos.turn_detection || {};
      ws.send(JSON.stringify({ type: "config", silence_ms: td.silence_duration_ms, threshold: td.threshold }));
      stopMic = startMic(stream, ws, AudioCtx);
      player.prepare?.();                     // set up the echo-cancelled output before the greeting plays
      dc.readyState = "open";
      emit({ type: "session.created", session: { id: id("cascade"), model: session.session?.model } });
      setTimeout(() => dc.onopen?.(), 0);
    } else if (m.type === "speech_started") {
      emit({ type: "input_audio_buffer.speech_started" });
      if (resp) cancel("turn_detected");    // barge-in, as the room session's interrupt_response
    } else if (m.type === "speech_paused") {
      early = transcribe(m.wav);
    } else if (m.type === "speech_resumed") {
      early = null;
    } else if (m.type === "speech_stopped") {
      heard(m.wav);
    }
  }

  function onClient(e) {
    if (e.type === "session.update") {
      const td = e.session?.audio?.input?.turn_detection;
      if (td && typeof td.create_response === "boolean") autoRespond = td.create_response;
      emit({ type: "session.updated", session: { model: session.session?.model } });
    } else if (e.type === "conversation.item.create") {
      const msg = chatMessage(e.item);
      if (msg) items.push(msg);
      const added = { ...e.item, id: e.item?.id || id("item") };
      emit({ type: "conversation.item.added", item: added });
    } else if (e.type === "response.create") {
      respond(e.response || {});
    } else if (e.type === "response.cancel" || e.type === "output_audio_buffer.clear") {
      cancel("client_cancelled");
    }
  }

  function close() {
    if (closed) return;
    closed = true; dc.readyState = "closed";
    if (resp) { resp.abort.abort(); resp = null; }
    try { stopMic?.(); } catch {}
    player.close();
    try { ws.close(); } catch {}
    fetchImpl(`${api}/aria-voice/end`, { method: "POST", headers, keepalive: true }).catch(() => {});
  }

  ws.onmessage = onService;
  ws.onclose = () => { if (!closed) dc.onclose?.(); };
  ws.onerror = () => emit({ type: "error", error: { message: "Local voice service unavailable." } });
  return { pc: { close, getSenders: () => [] }, dc };
}
