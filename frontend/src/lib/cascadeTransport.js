/**
 * Low-cost voice transport (docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md). Stands where the WebRTC peer connection
 * and its "oai-events" data channel stand in realtimeConnection.js, and produces the same Realtime events the
 * handler (realtimeMessageHandler.js) already understands - so Aria's tools, grounding, memory and receipts
 * are unchanged. Behind it: local VAD + TTS (room-node/aria_voice, ws://127.0.0.1:8794) and the backend's
 * receipted speech-to-text and text model (routes/aria_voice.py). No Realtime model is used.
 * Side-by-side audition only: chosen by ?aria_voice=cascade on the room page, never by default.
 */
export const VOICE_SERVICE_URL = "ws://127.0.0.1:8794";
const SENTENCE_END = /[.!?…]["')\]]?\s+/;

export function requestedTransport(search = typeof window !== "undefined" ? window.location.search : "") {
  return new URLSearchParams(search).get("aria_voice") === "cascade" ? "cascade" : null;
}

/** Realtime conversation items -> chat messages (what the backend's text model takes). */
export function chatMessage(item) {
  if (item?.type === "function_call_output") return { role: "tool", tool_call_id: item.call_id, content: String(item.output ?? "") };
  if (item?.type === "message" && (item.role === "user" || item.role === "assistant")) {
    const text = (item.content || []).map((c) => c.text || c.transcript || "").join(" ").trim();
    return text ? { role: item.role, content: text } : null;
  }
  return null;
}

/** Splits streamed text into finished sentences; returns [sentences, remainder]. */
export function takeSentences(buf) {
  const out = [];
  let m;
  while ((m = SENTENCE_END.exec(buf))) {
    out.push(buf.slice(0, m.index + m[0].length).trim());
    buf = buf.slice(m.index + m[0].length);
  }
  return [out, buf];
}

/** Plays PCM16 chunks back to back; stop() cuts playback at once. */
export function createPlayer(AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext)) {
  let ctx = null, next = 0, live = [], onIdle = null;
  return {
    set onIdle(fn) { onIdle = fn; },
    get playing() { return live.length > 0; },
    play(pcm16, rate) {
      ctx = ctx || new AudioCtx();
      const f = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) f[i] = pcm16[i] / 32768;
      const buf = ctx.createBuffer(1, f.length, rate);
      buf.copyToChannel(f, 0);
      const src = ctx.createBufferSource();
      src.buffer = buf; src.connect(ctx.destination);
      next = Math.max(next, ctx.currentTime + 0.03);
      src.start(next); next += buf.duration;
      live.push(src);
      src.onended = () => { live = live.filter((s) => s !== src); if (!live.length) onIdle?.(); };
    },
    stop() { const was = live.length > 0; live.forEach((s) => { try { s.onended = null; s.stop(); } catch {} }); live = []; next = 0; return was; },
    close() { this.stop(); try { ctx?.close(); } catch {} },
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

export function createCascadeConnection({ session, caos, stream, api, wsUrl = VOICE_SERVICE_URL,
  WebSocketImpl = WebSocket, fetchImpl = (...a) => fetch(...a), player = createPlayer(),
  AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext) }) {
  const headers = { "X-Aria-Voice-Token": session.token };
  const items = [];                         // the conversation, as chat messages
  let n = 0, rate = 22050, gen = 0, autoRespond = true, resp = null, stopMic = null, closed = false;
  const id = (p) => `${p}_${Date.now().toString(36)}_${++n}`;
  const dc = { readyState: "connecting", onopen: null, onmessage: null, onclose: null, send: (s) => onClient(JSON.parse(s)), close };
  const emit = (obj) => { if (!closed) setTimeout(() => dc.onmessage?.({ data: JSON.stringify(obj) }), 0); };
  const ws = new WebSocketImpl(wsUrl);
  ws.binaryType = "arraybuffer";
  player.onIdle = () => {               // between sentences the player idles too: only the reply's real end counts
    if (resp?.speaking && resp.done && resp.pending === 0) { finishAudio(resp); resp = null; }
  };

  function finishAudio(r) { r.speaking = false; emit({ type: "output_audio_buffer.stopped", response_id: r.id }); }

  function say(r, text) {
    if (!text) return;
    r.spoken.push(text); r.pending += 1;
    ws.send(JSON.stringify({ type: "speak", id: r.id, text }));
  }

  function cancel(reason) {
    const r = resp;
    if (!r) return false;
    resp = null; r.abort?.abort(); gen += 1;
    ws.send(JSON.stringify({ type: "stop" }));
    const wasPlaying = player.stop();
    if (wasPlaying || r.speaking) emit({ type: "output_audio_buffer.cleared", response_id: r.id });
    if (!r.done) emit({ type: "response.done", response: { id: r.id, status: "cancelled", status_details: { reason }, usage: null } });
    return true;
  }

  async function respond(opts = {}) {
    if (resp && !resp.done) return emit({ type: "error", error: { message: "Conversation already has an active response." } });
    const r = resp = { id: id("resp"), item: id("item"), spoken: [], pending: 0, text: "", buf: "", calls: [], done: false, speaking: false, gen };
    emit({ type: "response.created", response: { id: r.id } });
    const delta = (d) => { r.text += d; emit({ type: "response.output_audio_transcript.delta", response_id: r.id, item_id: r.item, delta: d });
      const [done, rest] = takeSentences(r.buf + d); r.buf = rest; done.forEach((s) => say(r, s)); };
    try {
      if (caos.greeting_line && opts.instructions && opts.instructions === caos.greeting?.instructions) delta(caos.greeting_line + " ");
      else await streamReply(r, opts, delta);
    } catch (e) {
      if (r.abort?.signal.aborted) return;
      emit({ type: "error", error: { message: `Low-cost voice: ${e.message}` } });
    }
    if (resp !== r) return;                 // cancelled meanwhile
    say(r, r.buf.trim()); r.buf = "";
    const text = r.text.trim();
    if (text || r.calls.length) items.push({ role: "assistant", content: text || null,
      ...(r.calls.length ? { tool_calls: r.calls.map((c) => ({ id: c.id, type: "function", function: { name: c.name, arguments: c.arguments } })) } : {}) });
    if (text) emit({ type: "response.output_audio_transcript.done", response_id: r.id, item_id: r.item, transcript: text });
    r.calls.forEach((c) => emit({ type: "response.function_call_arguments.done", response_id: r.id, call_id: c.id, name: c.name, arguments: c.arguments }));
    r.done = true;
    emit({ type: "response.done", response: { id: r.id, status: "completed", usage: null } });
    if (!r.pending && !player.playing) resp = null;
  }

  async function streamReply(r, opts, delta) {
    r.abort = new AbortController();
    const res = await fetchImpl(`${api}/aria-voice/respond`, { method: "POST", signal: r.abort.signal,
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ items, ...(opts.instructions ? { instructions: opts.instructions } : {}),
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

  async function heard(wavB64) {
    const item = id("item");
    emit({ type: "input_audio_buffer.speech_stopped", item_id: item });
    const bytes = Uint8Array.from(atob(wavB64), (c) => c.charCodeAt(0));
    let text = "";
    try {
      const res = await fetchImpl(`${api}/aria-voice/transcribe`, { method: "POST", headers: { ...headers, "Content-Type": "audio/wav" }, body: bytes });
      if (res.ok) text = (await res.json()).text || "";
    } catch {}
    if (closed) return;
    if (text) items.push({ role: "user", content: text });
    emit({ type: "conversation.item.input_audio_transcription.completed", item_id: item, transcript: text });
    if (text && autoRespond) respond();
  }

  function onService(ev) {
    if (typeof ev.data !== "string") {
      const view = new DataView(ev.data);
      if (view.getUint32(0, true) !== gen || !resp) return;      // audio of an interrupted reply
      if (!resp.speaking) { resp.speaking = true; emit({ type: "output_audio_buffer.started", response_id: resp.id }); }
      player.play(new Int16Array(ev.data.slice(4)), rate);
      return;
    }
    const m = JSON.parse(ev.data);
    if (m.type === "ready") {
      rate = m.sample_rate; gen = m.gen || 0;
      const td = caos.turn_detection || {};
      ws.send(JSON.stringify({ type: "config", silence_ms: td.silence_duration_ms, threshold: td.threshold }));
      stopMic = startMic(stream, ws, AudioCtx);
      dc.readyState = "open";
      emit({ type: "session.created", session: { id: id("cascade"), model: session.session?.model } });
      setTimeout(() => dc.onopen?.(), 0);
    } else if (m.type === "speech_started") {
      emit({ type: "input_audio_buffer.speech_started" });
      if (resp) cancel("turn_detected");    // barge-in, as the room session's interrupt_response
    } else if (m.type === "speech_stopped") {
      heard(m.wav);
    } else if (m.type === "spoken" && resp && m.id === resp.id) {
      resp.pending -= 1;
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
