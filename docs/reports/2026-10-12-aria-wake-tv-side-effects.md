# Aria wake / TV side-effect forensic report

**Observed:** Monday, October 12, 2026, approximately 7:17-8:24 PM America/Chicago  
**Scope:** Room 214 resident page, wake-triggered conversation start/end, TV IR commands, duplicate goodbye playback  
**Repository state inspected:** `a1576c71db5cdcaf39827305f9f9948056c15bbc`

## Owner observation

Michael reported that saying “Hey Aria” sometimes powered the TV off and, after a later change, lowered its volume without any TV request. Other wakes did not visibly affect the TV. He also reported one exchange with a second goodbye voice in the background.

These are owner-observed physical outcomes. Chat did not hear the room audio directly.

## Proven code path

1. Before `bff666b`, `Kiosk.jsx::beginConversation()` automatically sent `power=off` to every room TV/speaker whose stored state said it was on. That ran for every conversation start, including a wake-word start.
2. `bff666b` replaced the power command with `duckRoomAudio()`. For an IR TV exposing `volume_step`, that function sends 15 volume-down presses at every conversation start and records 15 volume-up presses for close. It deliberately does this even when stored power is `off`, because the adapter is one-way.
3. The first version awaited all 15 IR presses before continuing. `ea8e70c` moved the duck into the background after a five-second greeting delay was observed.
4. Issue #129 records a live Room 214 device receipt at 8:23:47 PM for `volume_step=-15` at wake and `volume_step=+15` at close. The IR adapter marks both unverified because it records what was sent, not what the TV physically did.
5. Therefore wake and device control are still directly coupled. The current volume movement is not an accidental model tool call; it is unconditional resident-page code.

## Duplicate goodbye finding already repaired

The earlier second goodbye voice had a separate proven cause. The local browser fallback said “Goodbye.” because the ending controller had not counted model audio that started before the `end_call` tool result was granted. `77e3351` passes the current playback state into `markEnding()` so already-playing model audio counts as heard and suppresses the browser fallback. Current code has one Realtime conversation path and a generation guard against orphan peer connections. A new duplicate-voice observation still requires a fresh session/event trace; it must not be inferred from the old incident.

## Required correction

- Starting or ending a conversation must issue **no TV or speaker command**.
- “Hey Aria” must only activate the existing conversation path.
- TV power and volume commands remain available only through an explicit resident request (or a separately authorized future policy with its own setting and receipt).
- Remove the stale `tv_auto_mute` capability claim from the room-companion blueprint.
- Add a regression check that the resident page contains no automatic duck/restore path while retaining the explicit device-command path.

## Verification required

1. Focused frontend regression test passes.
2. Full frontend suite and production build pass.
3. Source search shows no wake/start/end path calling TV power, volume, or mute.
4. No deployment or Room 214 runtime change is claimed until the corrected frontend revision is actually loaded and a real wake is observed with no device-command receipt.

## Implementation and local evidence

- Local implementation commit: `625880c04bbd28ce03ce7b740d883409649023b8`; published GitHub implementation commit: `436589ec00485f96a503466841d6ad1d3d79a4c7`.
- `Kiosk.jsx` no longer imports or invokes automatic audio duck/restore code. Conversation start changes only the call state; conversation end clears only conversation state.
- The obsolete `callAudioDuck.js` implementation and its behavior test were removed.
- `conversationDeviceBoundary.test.js` asserts that the automatic duck/restore symbols are absent while the explicit resident-requested device command path remains wired.
- The room-companion blueprint no longer advertises `tv_auto_mute`.
- Focused tests: 3 suites, 8 tests passed (`conversationDeviceBoundary`, `endControllerFallback`, `kioskDeviceControl`).
- Full frontend run: 93 suites / 642 tests passed. Five unrelated UI suites could not load because the available dependency tree resolved a newer `@radix-ui/primitive` subpath that Jest 27 cannot resolve; no test assertion failed.
- Production frontend build: compiled successfully (`main.71429e96.js`, `main.6ade4251.css`).
- `git diff --check`: passed.
- Room 214 load / physical wake acceptance: **NOT RUN**. No deployment or runtime mutation was performed.

