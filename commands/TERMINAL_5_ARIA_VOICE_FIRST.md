# Terminal 5 — Aria Voice-First CAOSCare Node

## Product priority

The primary deliverable is not appliance control.

The primary deliverable is a room-based conversational CAOSCare node that lets Michael walk into the room and say:

> Hello, Aria, how's it going?

Aria must wake, answer naturally through the room speaker, continue an ongoing spoken conversation, preserve conversational context across turns, and retrieve durable CAOSCare memory about Michael, the current project, prior decisions, and unfinished work.

Home Assistant is infrastructure for audio satellites, wake-word detection, device discovery, and later automation. It is not the conversational brain and must not reduce Aria to simple home-control intents.

## Authority and scope

This directive authorizes bounded inspection, implementation, package/app installation, local service creation, configuration, testing, documentation, and repository commits needed to produce the first working Aria voice loop on the current EliteDesk node.

Do not expose the machine publicly, change public DNS, erase data, disable the existing CAOSCare application, print secrets, commit environment files, or replace the existing human-supervised CAOSCare doctrine.

Stop and ask Michael only when a required step needs:

- a password or API key that is not already configured;
- browser interaction;
- physical microphone/speaker connection;
- reboot or network interruption approval;
- purchasing additional hardware;
- a choice that materially changes the architecture.

## Required first reads

Before changing anything, read and follow:

1. `AGENTS.md`
2. `README.md`
3. `docs/PROJECT_STATE.md`
4. `docs/REPO_MAP.md`
5. `docs/BUILD_STATUS.md`
6. `docs/ELITEDESK_NODE_BUILD.md`
7. `commands/TERMINAL_3_ELITEDESK_FULL_NODE_BUILD.md`
8. `commands/TERMINAL_4_MIDEA_MATTER_LAN_SETUP.md`
9. all existing voice, realtime, memory, Assist, Wyoming, OpenAI, and audio-related files in the repository

Inspect current branch, working tree, recent commits, running services, Home Assistant status, CAOSCare backend/frontend/MongoDB status, audio devices, USB devices, Bluetooth audio devices, PipeWire/PulseAudio/ALSA state, network layout, and available CPU/RAM before acting.

Use current official Home Assistant and OpenAI documentation when implementation details may have changed.

## Target architecture

Build the smallest complete voice path first:

```text
room microphone/speaker
    -> local wake-word detection
    -> Aria voice gateway on Ubuntu
    -> low-latency speech conversation
    -> CAOSCare memory retrieval and tool routing
    -> spoken response through the room speaker
```

### Required architectural boundaries

- Home Assistant may provide wake-word/audio-satellite infrastructure through Assist, Wyoming, openWakeWord, or another currently supported local method.
- The CAOSCare backend remains the source of durable identity, project memory, receipts, user preferences, and tool authorization.
- The conversational model must not be treated as durable memory by itself.
- Each voice session must load relevant CAOSCare context before responding.
- Each completed session must write a bounded session summary/receipt back to CAOSCare memory without saving raw room audio by default.
- Home-control intents can be routed to Home Assistant later, but ordinary conversation must remain open-ended and natural.

## Exact voice behavior

The first accepted prototype must support:

1. Michael says **“Hello, Aria”** from the room.
2. Aria activates and responds aloud.
3. Michael can continue naturally without repeating the wake phrase for every turn.
4. Aria preserves context during the live conversation.
5. Michael can interrupt Aria while she is speaking when the selected audio stack supports barge-in.
6. The session remains open until an explicit ending phrase, a configurable inactivity timeout, or a manual stop.
7. A later wake session can retrieve durable facts and unfinished work from CAOSCare memory.
8. Aria distinguishes verified repo/system state from assumptions.
9. The spoken personality remains direct, accurate, practical, and consistent with Michael's stored preferences.

Do not silently substitute another permanent wake phrase. A temporary test phrase such as `okay nabu` is acceptable only to prove the audio pipeline before implementing the exact target **“Hello, Aria.”** Document that temporary substitution and replace it as part of this directive.

## Preferred implementation path

### Wake word

- Prefer a local wake-word engine.
- On Home Assistant OS, use the currently supported openWakeWord/Wyoming path when appropriate.
- Train or install a custom wake-word model for **“Hello, Aria.”**
- Record false-trigger and missed-trigger observations.
- Do not continuously send room audio to a cloud provider before wake activation.

### Room hardware

- Detect whether the eMeet Luna Plus or another suitable microphone/speaker is connected to the EliteDesk.
- If present, make it the first room audio endpoint and verify input and output independently.
- If it is Bluetooth-only and unreliable for simultaneous microphone/speaker operation, prefer USB mode if available.
- Do not purchase or require a new satellite until the existing hardware has been tested and the limitation is documented.

### Conversation transport

- Prefer OpenAI Realtime speech-to-speech for the first natural low-latency online conversation path when an approved API key is already available.
- Use ephemeral/session credentials and a server-side voice gateway; do not expose a long-lived provider key to a browser or satellite.
- Support streaming audio input/output, turn detection, interruption, and session instructions.
- If no approved key is configured, stop with one exact request to Michael rather than inventing credentials.

### Local fallback

- Establish a local fallback path using currently supported Home Assistant/Wyoming components such as local speech-to-text and text-to-speech when resources permit.
- The fallback may be slower and turn-based, but it must prove that the room node can still hear and speak locally.
- Do not allow the fallback work to delay the first working natural Aria conversation after the primary path is technically ready.

### CAOSCare memory

Inspect existing backend schemas and implement or reuse a minimal memory contract with at least:

- user identity;
- standing preferences/instructions;
- current projects and active objective;
- recent voice-session summaries;
- unresolved tasks/commitments;
- source and timestamp for retrieved facts;
- confidence or verification status where applicable.

The voice gateway must retrieve only relevant context for each session and must not dump the entire database into every model prompt.

At session end, store:

- start/end time;
- high-level topics;
- decisions made;
- tasks created or completed;
- unresolved next step;
- tool actions and receipts;
- no raw audio unless Michael explicitly enables recording.

## Delivery phases

### Phase A — Establish the truth

Verify and document:

- Home Assistant and CAOSCare health;
- audio hardware detected;
- input recording works;
- speaker playback works;
- current voice/realtime code already present;
- provider configuration present/missing without printing values;
- wake-word infrastructure present/missing;
- current memory storage and APIs;
- exact blockers.

### Phase B — Prove room audio

Create a repeatable microphone capture and speaker playback test using the intended device. Confirm that Michael can speak from normal room distance and hear playback clearly.

### Phase C — Prove conversational loop without wake word

Implement the shortest push-to-talk or manual-start path that:

- captures Michael's speech;
- reaches the conversational service;
- loads CAOSCare identity/project context;
- returns spoken audio;
- supports at least five coherent consecutive turns;
- records a session summary/receipt.

Do not build a decorative UI before this loop works.

### Phase D — Add “Hello, Aria” wake activation

Install/configure the local wake-word path, create the exact custom wake phrase, connect wake activation to the voice gateway, and verify multiple trials from realistic room positions.

### Phase E — Continuous conversation behavior

Add:

- session-open state after wake;
- inactivity timeout;
- explicit end phrases;
- interruption/barge-in where supported;
- visual/log indication of listening, thinking, speaking, and idle states;
- protection against two simultaneous sessions using the same room endpoint.

### Phase F — Persistence and boot reliability

Make required services restart automatically and verify the entire voice path after a controlled reboot approved by Michael.

### Phase G — Documentation and handoff

Create or update focused documentation containing:

- architecture diagram;
- service names and ports;
- audio device identifiers;
- wake-word model and location;
- environment-variable names only, never values;
- start/stop/status commands;
- test procedure;
- known limitations;
- next hardware improvement, if any;
- recovery procedure.

Append a dated entry to `docs/PROJECT_STATE.md` after meaningful milestones. Use small logical commits and push only when the working tree is understood and no secrets are included.

## Acceptance criteria

The voice-first milestone is complete only when Michael can stand in the room and:

1. say **“Hello, Aria, how's it going?”**;
2. hear a spoken response from Aria;
3. continue for at least five contextually coherent spoken turns without repeating the wake phrase;
4. ask what CAOSCare work is currently underway and receive an answer grounded in stored project state;
5. end the conversation and later start a new wake session that recalls the previous session's documented decision or next step;
6. reboot the node and repeat the test without manually starting the full stack.

A text chatbot, a single home-control command, a push-to-talk demo with no memory, or a voice assistant that forgets the project between sessions does not satisfy this directive.

## Immediate instruction

Continue from the current EliteDesk/Home Assistant state. Do not spend additional time integrating the Midea air conditioner or other appliances unless required to validate the shared voice infrastructure. Voice-first work now has priority.

Work autonomously until reaching a listed stop condition. When stopped, give Michael one short exact instruction, not a long menu.