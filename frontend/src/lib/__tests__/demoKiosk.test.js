import {
  createTypedTurnState, sendTypedTurn, markResponseRequested,
  onTypedEcho, onTypedResponseCreated, onTypedResponseDone, typedTurnFromMessage, TYPED_TURN_CLASS,
} from "../realtimeTypedTurn";
import { demoRoomView, demoRoomCaption } from "../demoRoom";

describe("typed input goes into the same Realtime conversation", () => {
  test("idle session: user message then one reply request", () => {
    const sent = [];
    const state = createTypedTurnState();
    expect(sendTypedTurn(state, (e) => sent.push(e), "  Turn the light on.  ")).toBe(true);
    expect(sent).toEqual([
      { type: "conversation.item.create",
        item: { type: "message", role: "user", content: [{ type: "input_text", text: "Turn the light on." }] } },
      { type: "response.create" },
    ]);
    expect(state.responseActive).toBe(true);
  });

  test("empty text sends nothing", () => {
    const sent = [];
    expect(sendTypedTurn(createTypedTurnState(), (e) => sent.push(e), "   ")).toBe(false);
    expect(sent).toEqual([]);
  });

  const creates = (sent) => sent.filter((e) => e.type === "response.create").length;

  test("typed during the greeting, answered by a response created after it (the real trace): no extra create", () => {
    const sent = []; const send = (e) => sent.push(e);
    const state = createTypedTurnState();
    markResponseRequested(state, send);            // the greeting, sent on connect
    sendTypedTurn(state, send, "Turn the light on.");
    expect(creates(sent)).toBe(1);                 // waits: a response is already active
    onTypedEcho(state);                            // server added the typed message
    onTypedResponseCreated(state);                 // this response sees it
    onTypedResponseDone(state, send, { output: [{ type: "function_call", name: "toggle_light" }] });
    expect(creates(sent)).toBe(1);                 // the tool path asks for the next response itself
    expect(state.replyPending).toBe(false);
  });

  test("typed while a response runs that started before it: the reply is requested when it finishes", () => {
    const sent = []; const send = (e) => sent.push(e);
    const state = createTypedTurnState();
    onTypedResponseCreated(state);                 // Aria already talking
    sendTypedTurn(state, send, "Turn the light off.");
    onTypedEcho(state);                            // no newer response created after the echo
    onTypedResponseDone(state, send, { output: [{ type: "message" }] });
    expect(creates(sent)).toBe(1);
    expect(state.replyPending).toBe(false);
  });

  test("an unanswered reply is not requested when the finishing response ended in a tool call", () => {
    const sent = []; const send = (e) => sent.push(e);
    const state = createTypedTurnState();
    onTypedResponseCreated(state);
    sendTypedTurn(state, send, "Turn the TV on.");
    onTypedResponseDone(state, send, { output: [{ type: "function_call" }] });
    expect(creates(sent)).toBe(0);                 // tool path's response will carry it
    onTypedEcho(state);
    onTypedResponseCreated(state);                 // that response sees the typed message
    expect(state.replyPending).toBe(false);
  });

  test("a response finishing with nothing typed sends nothing", () => {
    const sent = [];
    const state = createTypedTurnState();
    onTypedResponseCreated(state);
    onTypedResponseDone(state, (e) => sent.push(e));
    expect(sent).toEqual([]);
    expect(state.responseActive).toBe(false);
  });

  test("the server's echo of a typed message is recognised; spoken items are not", () => {
    const typed = { type: "conversation.item.added",
      item: { id: "item_1", type: "message", role: "user", content: [{ type: "input_text", text: "Turn the light on." }] } };
    expect(typedTurnFromMessage(typed)).toEqual({ id: "item_1", text: "Turn the light on." });
    expect(typedTurnFromMessage({ ...typed, type: "conversation.item.created" })).toEqual({ id: "item_1", text: "Turn the light on." });
    const spoken = { type: "conversation.item.added",
      item: { id: "item_2", type: "message", role: "user", content: [{ type: "input_audio", transcript: null }] } };
    expect(typedTurnFromMessage(spoken)).toBeNull();
    const aria = { type: "conversation.item.added",
      item: { id: "item_3", type: "message", role: "assistant", content: [{ type: "output_text", text: "hi" }] } };
    expect(typedTurnFromMessage(aria)).toBeNull();
    expect(TYPED_TURN_CLASS.suspect).toBe(false);
  });
});

describe("demo room view shows only stored device state", () => {
  const devices = [
    { kind: "light", state: { power: "on", brightness: 60 } },
    { kind: "thermostat", state: { power: "on", temperature: 72 } },
    { kind: "tv", state: { power: "off", volume: 20, channel: 3, input: "TV" } },
    { kind: "blinds", state: { position: 0 } },
  ];

  test("each device kind maps to its visual state", () => {
    const v = demoRoomView(devices);
    expect(v.light).toEqual({ on: true, brightness: 60 });
    expect(v.thermostat).toEqual({ on: true, temperature: 72 });
    expect(v.tv.on).toBe(false);
    expect(v.blinds.position).toBe(0);
    expect(demoRoomCaption(v)).toEqual(["Light on (60%)", "Thermostat 72°F", "TV off", "Blinds closed"]);
  });

  test("light off reads off", () => {
    const v = demoRoomView([{ kind: "light", state: { power: "off", brightness: 80 } }]);
    expect(v.light.on).toBe(false);
    expect(demoRoomCaption(v)).toEqual(["Light off"]);
  });

  test("missing and offline devices are absent, never invented", () => {
    const v = demoRoomView([{ kind: "light", online: false, state: { power: "on" } }]);
    expect(v.light).toBeNull();
    expect(v.tv).toBeNull();
    expect(demoRoomCaption(v)).toEqual([]);
  });
});
