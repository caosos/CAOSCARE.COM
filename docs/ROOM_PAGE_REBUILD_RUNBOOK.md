# Room page rebuild runbook (frontend only)

For the always-on Room 214 page served by `aria-wake-page.service` on :3002 from `~/.cache/aria-wake/build`. The agent runs this, not the owner. It needs ONE explicit owner authorization per rebuild because it changes what the live Room page does.

## What changes, what restarts
* Builds `frontend/` of the integration checkout (commit recorded in the receipt) into `~/.cache/aria-wake/build.new`, then swaps it in. The page server reads files per request, so no service restart is needed for new visitors.
* The already-open kiosk window keeps the old code until it reloads, so the last step restarts **`aria-wake-page.service` and `aria-wake-kiosk.service`** (page server and its headless Chrome): about 10 seconds with no Room page. **The wake listener `aria-wake.service` is NOT restarted** and keeps hearing "Hey Aria" the whole time.
* Not touched: backend :8092, Home Assistant, devices, wake threshold (0.05 / 1.5), listener config.

## Steps (agent)
1. Preconditions: integration HEAD == origin and tests pass; record `git rev-parse HEAD`.
2. Live-call check (ctl.sh does it too): no lease with status active/activating seen in the last 45 s. If one exists, wait and retry; never use `--force`.
3. `room-node/aria_wake/ctl.sh rebuild` (refuses during a live call). Success prints the built commit.
4. Verify the new build before switching the window: `curl -s localhost:3002/ | grep -o 'main\\.[a-z0-9]*\\.js'` differs from the previous one, and that bundle contains `local_end` / `end_call_corroborated`.
5. `room-node/aria_wake/ctl.sh restart-page` (also refuses during a live call).
6. Verify: both units `active`, `GET localhost:3002/api/health` ok, listener journal shows `wake_ws_client_connected` again, and no `mode_conversation` stuck.
7. Receipt: add a dated PROJECT_STATE entry (who authorized, commit, previous/new bundle name, check results). Then ask the owner for the short live acceptance: say "Hey Aria", talk briefly, say "Goodbye" - the call must end at once, then "Hey Aria" starts a fresh call.

## Rollback (seconds)
`ctl.sh rebuild` keeps the previous build at `~/.cache/aria-wake/build.prev`.
`cd ~/.cache/aria-wake && mv build build.bad && mv build.prev build && ~/CAOSCARE-INTEGRATION/room-node/aria_wake/ctl.sh restart-page`
(or `ctl.sh restart-page` after the swap). A failed build leaves the old build in place.

## Optional flags (only with owner approval, build time)
`REACT_APP_TRANSCRIPTION_HINT=1` (vocabulary hint, language not pinned). `REACT_APP_TRANSCRIPTION_LANGUAGE=en` is NOT recommended (breaks Spanish practice). `REACT_APP_CLAIM_INTERRUPTER` stays off.
