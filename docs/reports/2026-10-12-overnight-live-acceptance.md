# Overnight live acceptance — Room 214 voice settings, demo room and staff side (2026-10-12)

Owner approval: Michael, in the coordinator terminal: "yes, switch Room 214 to gpt-realtime-2.1 with marin,
turn on the 10-minute continuity and owner v2, and run the test calls".

## What changed on the EliteDesk development stack
- `backend/.env` (gitignored; backup `backend/.env.bak-20261012-012212`): `OPENAI_REALTIME_MODEL=gpt-realtime-2.1`,
  `CAOSCARE_REALTIME_VOICE=marin`, `CAOSCARE_CONTINUITY_RECENT_MINUTES=10`, `CAOSCARE_ARIA_OWNER_V2=1`.
  Not enabled: `CAOSCARE_CALL_TOOL`, research provider (not in the approval).
- Code: `5736b03` (voice can be set for every session; the page always asks for "shimmer"), `ec4a8d4` (a demo-room
  request is current while recent, it was hidden as past SIM work), `d02325f` (Aria says a just-finished request was
  taken care of; history no longer shows an invented "Started" step), `aba31a8` (auth tests pin the default session).
- Dev backend restarted with `scripts/restart_dev_backend.sh`; runtime `aba31a8`, clean tree, 0 leases at restart,
  log `/tmp/room214_backend_aba31a8.log`. Wake listener and Room 214 page/kiosk services not touched.
- **Rollback:** delete the four lines above (or restore the `.env.bak` copy) and run `scripts/restart_dev_backend.sh`.

## Calls (typed into `/kiosk/demo` in headless Chrome, fake mic, muted output — typed input, not spoken audio)
| Session | Asked | Result |
|---|---|---|
| rt_obado531_1791786228696 | Conway fact, time, weather, light on, 20-min tea timer, goodbye | each tool called and returned ok; call ended on goodbye |
| rt_4zj1bpm8_1791786294168 | "I'm back, what were we talking about?" | recalled weather, light and tea timer (10-minute continuity) |
| rt_711hyfr7_1791786340406 | "I need help going to the bathroom." | `request_staff_help` nursing/high → task_057363d94f5c, receipt `resident_request_created` |
| rt_zrvx37m0_1791786562628 | after a staff claim | "seen and taken on by staff, work hasn't started" (true) |
| rt_630maam2_1791786682736 | after completion (before fix) | "no open request on record" — true but did not say it was done |
| rt_fiaov1lb_1791786921828 | after completion (after fix) | "the bathroom request was already handled and closed" |

## Staff side (Claude in Chrome, Michael's Owner session, staff pages only)
Nursing queue showed the request (after `ec4a8d4`); Claim → Complete with a note; history shows
Created → Claimed → Note → Completed, 3 receipts. Screens: `assets/2026-10-12-overnight/01–03`.
Live operations, Nursing scenario: Start → Pause (held) → Step (one step, stayed paused) → Resume (ran) → finished 6/6,
each step with a receipt (`04–06`). Stop was clicked after the run had already finished, so a mid-run Stop was not
exercised tonight (covered by the SIM tests).

## Defects found
1. Fixed: demo-room requests hidden from the Nursing queue (`ec4a8d4`).
2. Fixed: Aria answered "no open request" after a request was completed (`d02325f`).
3. Fixed: history showed "Started" after "Completed" when work was completed from pending (`d02325f`).
4. Fixed (`8a06ad1`, `40c3fec`): Aria said nursing would "come help" and called the request "sent" while the notice was
   simulated. The create response now carries the real notice state; retest rt_ih7vi9zz_1791787206391: "It's on the
   nursing list now… no one has picked it up yet, so I can't say someone is on the way."
7. Fixed (`d01796b`): on a phone the action buttons cut the request title off; it now wraps (`07-nurse-staff-390.png`,
   nurse `/staff` at 390 and 1280: no overflow, no failed API calls).
5. Open: a fake-mic echo became a stray user turn ("Hallo.", "はい।") — test harness artifact, not a resident path.
6. Open: the claim guard flags the bare word "weather" even after `get_weather` ran (known false positive).

## Not done / blocked (unchanged)
Music (no Home Assistant `media_player`), AC (Midea unavailable), real email (`RESEND_API_KEY` unset), calls
(no Asterisk/Twilio/SIP), live research (provider unset), spoken audio in Room 214 (needs Michael). One demo request (task_134116c5c444) was left open in the Nursing queue.

## Gates
Backend gate at `ec4a8d4`: 588 passed / 2 failed / 31 skipped; the 2 were the auth tests reading the new `.env`
flags, fixed in `aba31a8` (that file 8/8 with the flags loaded). New tests pass. Frontend 87 suites / 626.
Production unchanged (`ff87c22`).

Final gate at `40c3fec` (backend unchanged since): backend 591 passed / 0 failed / 31 skipped; frontend 87 suites / 627; build compiled. Dev backend `8a06ad1`.
