// Typed input into the SAME Realtime conversation as voice.
//
// Typing does not bypass Aria: the text becomes a normal user message in
// the live session and Aria answers it with the same tools she uses for
// speech. The server echoes the message back as a conversation item, and
// realtimeMessageHandler.js treats that echo like a completed voice
// transcript (transcript line, tool grounding, turn persistence), so the
// grounding guards (end_call, volume, which-light) see the typed words
// exactly as they would see spoken ones.
//
// Asking for a reply while Aria is still producing one is rejected by the
// server, and any server error ends the kiosk call. So when a response is
// already running, the reply waits. It is satisfied by any response the
// server creates after the typed message is in the conversation (that
// response sees it); only if none comes is one requested when the current
// response finishes - and not when that response ended in a tool call,
// because the tool path requests the next response itself.

function userMessage(text) {
  return { type: "conversation.item.create",
    item: { type: "message", role: "user", content: [{ type: "input_text", text }] } };
}

export function createTypedTurnState() {
  return { responseActive: false, replyPending: false, echoSeen: false };
}

// Sends one typed turn. Returns false when there is nothing to send.
export function sendTypedTurn(state, send, text) {
  const clean = String(text || "").trim();
  if (!clean) return false;
  send(userMessage(clean));
  if (state.responseActive) { state.replyPending = true; state.echoSeen = false; }
  else markResponseRequested(state, send);
  return true;
}

// Any response.create we send (greeting or typed) counts as active at once,
// before the server's response.created arrives.
export function markResponseRequested(state, send) {
  send({ type: "response.create" });
  state.responseActive = true;
}

// The server has added our typed message to the conversation.
export function onTypedEcho(state) {
  state.echoSeen = true;
}

export function onTypedResponseCreated(state) {
  state.responseActive = true;
  if (state.replyPending && state.echoSeen) state.replyPending = false;
}

export function onTypedResponseDone(state, send, response) {
  state.responseActive = false;
  const endedInToolCall = (response?.output || []).some((o) => o.type === "function_call");
  if (state.replyPending && !endedInToolCall) {
    state.replyPending = false;
    markResponseRequested(state, send);
  }
}

// Returns {id, text} when `msg` is the server's echo of a typed user
// message, else null. Spoken turns (input_audio content) never match.
export function typedTurnFromMessage(msg) {
  if (msg?.type !== "conversation.item.added" && msg?.type !== "conversation.item.created") return null;
  const item = msg.item;
  if (!item || item.role !== "user" || item.type !== "message") return null;
  const part = (item.content || []).find((c) => c.type === "input_text");
  if (!part || !part.text) return null;
  return { id: item.id, text: part.text };
}

// A typed turn is never an echo of Aria's own audio.
export const TYPED_TURN_CLASS = { suspect: false, reason: "typed" };
