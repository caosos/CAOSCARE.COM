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
 * removes her own voice and it never reads as the resident barging in (Room 214, 2026-10-17 rt_hyovgwag).
 * Ready only once the peers are connected - audio sent before that goes nowhere. */
async function echoCancelledOutput(ctx, audioEl, RTC, waitMs) {
  const dest = ctx.createMediaStreamDestination();
  const a = new RTC(), b = new RTC();
  const close = () => { try { a.close(); b.close(); audioEl.srcObject = null; } catch {} };
  try {
    a.onicecandidate = (e) => e.candidate && b.addIceCandidate(e.candidate).catch(() => {});
    b.onicecandidate = (e) => e.candidate && a.addIceCandidate(e.candidate).catch(() => {});
    b.ontrack = (e) => { audioEl.srcObject = e.streams[0]; audioEl.play?.().catch(() => {}); };
    dest.stream.getTracks().forEach((t) => a.addTrack(t, dest.stream));
    await a.setLocalDescription(await a.createOffer());
    await b.setRemoteDescription(a.localDescription);
    await b.setLocalDescription(await b.createAnswer());
    await a.setRemoteDescription(b.localDescription);
    await new Promise((ok, no) => {
      const timer = setTimeout(() => no(new Error("loopback not connected")), waitMs);
      const check = () => {
        if (a.connectionState === "connected") { clearTimeout(timer); ok(); }
        else if (a.connectionState === "failed") { clearTimeout(timer); no(new Error("loopback failed")); }
      };
      a.onconnectionstatechange = check; check();
    });
  } catch (e) { close(); throw e; }
  return { node: dest, close };
}

const LEAD = 0.05;                 // s: how far ahead of the audio clock a piece is scheduled
export const PREBUFFER_MS = 200;   // audio held back before (re)starting after the player ran dry; never dropped
const DUCK = 0.3;                  // her volume while sound over her voice is checked for words

/** Plays PCM16 back to back on the audio clock; stop() cuts playback at once. With an audio element and WebRTC
 * available, the sound goes through the echo-cancelled path above, else (or if it never connects) to the speakers. */
export function createPlayer({ AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext),
  audioEl = null, RTC = typeof window !== "undefined" && window.RTCPeerConnection, loopbackWaitMs = 1500 } = {}) {
  let ctx = null, out = null, sink = null, gain = null, next = 0, live = [], onIdle = null;
  const ready = () => {
    if (!ctx) {
      ctx = new AudioCtx();
      out = (audioEl && RTC ? echoCancelledOutput(ctx, audioEl, RTC, loopbackWaitMs).catch(() => null) : Promise.resolve(null))
        .then((s) => (sink = s));
    }
    return out;
  };
  const output = () => {                  // her volume control, in front of the (echo-cancelled) output
    const to = sink ? sink.node : ctx.destination;
    if (!ctx.createGain) return to;
    if (!gain) { gain = ctx.createGain(); gain.connect(to); }
    return gain;
  };
  const level = (v) => gain && gain.gain.setTargetAtTime(v, ctx.currentTime, 0.03);
  return {
    set onIdle(fn) { onIdle = fn; },
    get playing() { return live.length > 0; },
    get output() { return sink ? "echo_cancelled" : "direct"; },
    prepare() { return ready(); },
    now() { return ctx ? ctx.currentTime : 0; },
    ahead() { return ctx ? Math.max(0, next - ctx.currentTime) : 0; },
    /** Schedules after what is already queued (call once prepare() has resolved). Returns where it sits on the
     * audio clock and the silence before it - an underrun when the queue ran dry first. */
    play(pcm16, rate) {
      ready();
      const f = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) f[i] = pcm16[i] / 32768;
      const buf = ctx.createBuffer(1, f.length, rate);
      buf.copyToChannel(f, 0);
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(output());
      const start = Math.max(next, ctx.currentTime + LEAD), gap = next > 0 ? start - next : 0;
      src.start(start); next = start + buf.duration;
      live.push(src);
      src.onended = () => { live = live.filter((x) => x !== src); if (!live.length) onIdle?.(); };
      return { start, end: next, gap };
    },
    /** Lowers (or restores) her voice without stopping it. */
    duck(on) { level(on ? DUCK : 1); },
    stop() { const was = live.length > 0; live.forEach((x) => { try { x.onended = null; x.stop(); } catch {} }); live = []; next = 0; level(1); return was; },
    close() { this.stop(); out?.then((x) => x?.close()); try { ctx?.close(); } catch {} },
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

function joinSamples(chunks) {
  if (chunks.length === 1) return chunks[0];
  const out = new Int16Array(chunks.reduce((n, c) => n + c.length, 0));
  let at = 0;
  chunks.forEach((c) => { out.set(c, at); at += c.length; });
  return out;
}
const ms = (s) => Math.round(s * 1000);

export function createCascadeConnection({ session, caos, stream, api, audioEl = null, wsUrl = VOICE_SERVICE_URL,
  WebSocketImpl = WebSocket, fetchImpl = (...a) => fetch(...a), player = createPlayer({ audioEl }), log = () => {},
  diagnostics = false,
  AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext) }) {
  const headers = { "X-Aria-Voice-Token": session.token };
  const rate = session.audio_sample_rate || 24000;
  const items = [];                         // the conversation, as chat messages
  let n = 0, autoRespond = true, resp = null, stopMic = null, closed = false;
  // Sound over her voice: {r, outcome}. Her own voice from the room speaker reaches the microphone too (Room 214
  // 2026-10-17 rt_sf8ft3v6: 7 of 9 interruptions had no words), so while she is audible sound only lowers her
  // voice; words - at the speaker's first pause or turn end - stop her. Silent, she stops at once, as before.
  let barge = null;
  const id = (p) => `${p}_${Date.now().toString(36)}_${++n}`;
  const dc = { readyState: "connecting", onopen: null, onmessage: null, onclose: null, send: (s) => onClient(JSON.parse(s)), close };
  const emit = (obj) => { if (!closed) setTimeout(() => dc.onmessage?.({ data: JSON.stringify(obj) }), 0); };
  const ws = new WebSocketImpl(wsUrl);
  player.onIdle = () => {                   // the player also runs dry between sentences: only the reply's end counts
    const r = resp;
    if (r?.speaking && r.done && !r.queue.length && !r.pump) finish(r);
  };

  function finishAudio(r) { r.speaking = false; emit({ type: "output_audio_buffer.stopped", response_id: r.id }); }
  const wake = (o, k) => { const w = o[k]; o[k] = null; w?.(); };

  /** What actually reached the speaker, read off the audio clock: sentences played to their end, and how far into
   * the one playing now. Queued or failed audio is not "heard". */
  function account(r) {
    const now = player.now?.() ?? Infinity;
    const heard = [];
    let partial = 0;
    r.sentences.forEach((e) => {
      if (e.startAt == null || e.startAt >= now) return;
      if (e.ended && !e.failure && !e.chunks.length && e.endAt <= now + 1e-6) heard.push(e.text);
      else partial = ms(Math.min(now, e.endAt) - e.startAt);
    });
    return { heard, partial };
  }

  /** One metadata-only playback receipt per reply: timing, buffering, failures and outcome - never its words. */
  function receipt(r, outcome, reason, { heard, partial }) {
    if (r.logged || !r.sentences.length) return;
    r.logged = true;
    const st = r.stats;
    log("cascade_playback", { responseId: r.id, meta: { transport: "cascade", outcome, ...(reason ? { reason } : {}),
      output: player.output ?? null, sentences: r.sentences.length, sentences_heard: heard.length, partial_ms: partial,
      failed: r.sentences.filter((e) => e.failure && e.failure !== "interrupted").length,
      first_audio_ms: st.firstStart == null ? null : ms(st.firstStart - r.t0), audio_ms: ms(st.audio),
      underruns: st.underruns, underrun_ms: ms(st.underrunS), max_sentence_gap_ms: ms(st.maxSentenceGap),
      max_queue_depth: st.maxQueue, max_buffered_ms: ms(st.maxAhead) } });
  }

  /** The reply has finished playing: only what was heard stays in the conversation. */
  function finish(r) {
    const a = account(r);
    if (r.speaking) finishAudio(r);
    if (r.sentences.some((e) => e.failure)) settle(r, a.heard.join(" ").trim());
    receipt(r, "completed", null, a);
    if (resp === r) resp = null;
  }

  function settle(r, heard) {
    if (r.itemIndex == null) return;
    const it = items[r.itemIndex];
    if (it.tool_calls) it.content = heard || null;
    else if (heard) it.content = heard;
    else { items.splice(r.itemIndex, 1); r.itemIndex = null; }
  }

  function failed(r, e, reason, extra = {}) {
    if (e.failure) return;
    e.failure = reason;
    log("cascade_speech_failed", { responseId: r.id, meta: { transport: "cascade", reason, chars: e.text.length,
      bytes: e.bytes, ...extra } });
  }

  // Every finished sentence is requested at once; sentences play strictly in order as their audio streams in.
  function say(r, text, fixed = false) {
    if (!text || resp !== r) return;
    const e = { text, chunks: [], ended: false, wake: null, bytes: 0, complete: false, failure: null, startAt: null, endAt: null };
    r.queue.push(e); r.sentences.push(e); r.said += 1;
    r.stats.maxQueue = Math.max(r.stats.maxQueue, r.queue.length);
    let late = 0;
    fetchImpl(`${api}/aria-voice/speak`, { method: "POST", signal: r.abort.signal,
      headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ text, fixed }) })
      .then(async (res) => {
        if (!res.ok) return failed(r, e, "http_error", { status: res.status });
        if (!res.body) return failed(r, e, "no_body");
        const reader = res.body.getReader();
        let carry = null;
        for (;;) {
          const { value, done } = await reader.read();
          if (done) { e.complete = true; break; }
          if (resp !== r) { late += 1; try { reader.cancel?.()?.catch?.(() => {}); } catch {} break; }   // cancelled speech
          e.bytes += value.length;
          let bytes = carry ? joinBytes(carry, value) : value;
          carry = null;
          if (bytes.length % 2) { carry = bytes.slice(-1); bytes = bytes.slice(0, -1); }
          if (bytes.length) { e.chunks.push(new Int16Array(bytes.slice().buffer)); wake(e, "wake"); }
        }
        if (e.complete && !e.bytes) failed(r, e, "empty");
      })
      .catch(() => { if (!r.abort.signal.aborted) failed(r, e, "network"); })
      .finally(() => {
        if (!e.complete && !e.failure) failed(r, e, "interrupted", { late_chunks: late });
        e.ended = true; wake(e, "wake");
      });
    if (r.pump) wake(r, "wakePump"); else r.pump = pump(r);
  }

  // Audio is scheduled as it arrives while the player still has some queued; once it has run dry (reply start, or an
  // underrun) it waits for PREBUFFER_MS - or the sentence's end - so a slow stream rebuffers once instead of
  // stuttering after every chunk. Nothing is dropped to catch up.
  async function pump(r) {
    await player.prepare?.();               // never play before the echo-cancelled output carries sound
    const st = r.stats;
    while (resp === r) {
      const e = r.queue[0];
      if (!e) { if (r.done) break; await new Promise((ok) => { r.wakePump = ok; }); continue; }
      while (resp === r) {
        const held = e.chunks.reduce((k, c) => k + c.length, 0) / rate * 1000;
        if (held && (e.ended || player.ahead() > 0 || held >= PREBUFFER_MS)) {
          if (!r.speaking) { r.speaking = true; emit({ type: "output_audio_buffer.started", response_id: r.id }); }
          const t = player.play(joinSamples(e.chunks.splice(0)), rate);
          if (st.firstStart == null) st.firstStart = t.start;
          else if (e.startAt == null) st.maxSentenceGap = Math.max(st.maxSentenceGap, t.gap);
          else if (t.gap > 1e-6) { st.underruns += 1; st.underrunS += t.gap; }
          if (e.startAt == null) e.startAt = t.start;
          e.endAt = t.end; st.audio += t.end - t.start;
          st.maxAhead = Math.max(st.maxAhead, player.ahead());
          continue;
        }
        if (e.ended && !e.chunks.length) break;
        await new Promise((ok) => { e.wake = ok; });
      }
      r.queue.shift();
    }
    r.pump = null;
    if (resp === r && r.done && !player.playing) finish(r);
  }

  function cancel(reason) {
    const r = resp;
    if (!r) return false;
    const a = account(r);
    resp = null; r.abort.abort();
    wake(r, "wakePump"); r.queue.forEach((e) => wake(e, "wake"));
    const wasPlaying = player.stop();
    if (wasPlaying || r.speaking) emit({ type: "output_audio_buffer.cleared", response_id: r.id });
    receipt(r, "cancelled", reason, a);
    // Only what played to the end counts as said; queued, failed or cut-off speech is not in the conversation.
    const heard = a.heard.join(" ").trim();
    if (!r.done) {
      if (heard) {
        items.push({ role: "assistant", content: heard });
        emit({ type: "response.output_audio_transcript.done", response_id: r.id, item_id: r.item, transcript: heard });
      }
      emit({ type: "response.done", response: { id: r.id, status: "cancelled", status_details: { reason }, usage: null } });
    } else settle(r, heard);
    return true;
  }

  async function respond(opts = {}) {
    if (resp && !resp.done) return emit({ type: "error", error: { message: "Conversation already has an active response." } });
    if (resp) cancel("superseded");         // a finished reply still playing gives way to the next one
    const r = resp = { id: id("resp"), item: id("item"), queue: [], sentences: [], said: 0, text: "", buf: "", calls: [],
      done: false, speaking: false, pump: null, wakePump: null, itemIndex: null, abort: new AbortController(),
      t0: player.now?.() ?? 0, logged: false,
      stats: { firstStart: null, audio: 0, underruns: 0, underrunS: 0, maxSentenceGap: 0, maxQueue: 0, maxAhead: 0 } };
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
    if (r.pump) wake(r, "wakePump"); else if (!player.playing) finish(r);
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
    const b = barge; barge = null;
    if (b) {
      stopFor(b, text);
      if (!b.outcome) { b.outcome = "ignored"; player.duck?.(false); }
      log("cascade_barge_in", { responseId: b.r.id, meta: { transport: "cascade", outcome: b.outcome,
        was_playing: b.was_playing, heard_ms: ms(b.r.stats.audio), words: wordCount(text) } });
    }
    if (b?.outcome === "ignored") {         // no words: not a turn - she carries on
      emit({ type: "conversation.item.input_audio_transcription.completed", item_id: item, transcript: "" });
      return;
    }
    if (text) items.push({ role: "user", content: text });
    emit({ type: "conversation.item.input_audio_transcription.completed", item_id: item, transcript: text });
    if (text && autoRespond) {
      if (resp && !resp.done) cancel("next_turn");   // a reply still being written gives way to the newer turn
      respond();
    }
  }

  const wordCount = (text) => (text.match(/[\p{L}\p{N}]+/gu) || []).length;
  function stopFor(b, text) {               // words over her voice stop her
    if (b.outcome || !wordCount(text)) return;
    b.outcome = "stopped";
    if (resp === b.r) cancel("turn_detected"); else player.duck?.(false);
  }

  function onService(ev) {
    const m = JSON.parse(ev.data);
    if (m.type === "ready") {
      const td = caos.turn_detection || {};
      ws.send(JSON.stringify({ type: "config", silence_ms: td.silence_duration_ms, threshold: td.threshold,
        ...(diagnostics ? { diagnostics: true } : {}) }));
      stopMic = startMic(stream, ws, AudioCtx);
      player.prepare?.();                     // set up the echo-cancelled output before the greeting plays
      dc.readyState = "open";
      emit({ type: "session.created", session: { id: id("cascade"), model: session.session?.model } });
      setTimeout(() => dc.onopen?.(), 0);
    } else if (m.type === "speech_started") {
      emit({ type: "input_audio_buffer.speech_started" });
      if (!resp || barge) return;
      if (player.playing) { barge = { r: resp, outcome: null, was_playing: true }; player.duck?.(true); }
      else { barge = { r: resp, outcome: "stopped", was_playing: false }; cancel("turn_detected"); }
    } else if (m.type === "speech_paused") {
      early = transcribe(m.wav);
      if (barge && !barge.outcome) { const b = barge; early.then((t) => { if (!closed) stopFor(b, t); }); }
    } else if (m.type === "speech_resumed") {
      early = null;
    } else if (m.type === "speech_stopped") {
      heard(m.wav);
    } else if (m.type === "diag" && diagnostics) {   // numbers only (aria_voice Diag); never affects the call
      try { Promise.resolve(log("cascade_vad_diag", { meta: { transport: "cascade", ...m.data } })).catch(() => {}); } catch {}
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
