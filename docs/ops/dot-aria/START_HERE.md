# START HERE — Dot Aria bounded CAOSCare channel

Checkpoint date: 2026-10-19 (America/Chicago)

**October 20 update:** the original review/evidence below is historical. Current connection preparation is in `/home/caoscare-1/CAOSCARE-DOT-ARIA-CONNECT`, branch `feature/dot-aria-caoscare-connect`; see README's October 20 section for the actual 30-test gate and runtime checks. No activation has occurred. The original Michael-owned checkout is preserved. Current Voice target is regular ChatGPT, not the dot page.

## Review target

- Checkout: `/home/michaelos/CAOSCARE-arya-call-integration`
- Branch: `feature/dot-aria-caoscare-channel`
- Unchanged base: `bc79f9eb0dbe02735e2d9b5d7b49994e1a96f01c` (`origin/integration/2026-09-27` when work began)
- Review commit: see the handoff receipt and `git rev-parse HEAD`; no push, merge or deployment was performed.
- Comparison checkout: `/home/michaelos/CAOSCARE-dot-aria-baseline`, detached at the unchanged base; no edits.

The six-tool backend and Home Assistant package are built. They are **not installed, loaded, exposed or connected to Arya**. No credential was generated. All tests use a fresh scratch database and synthetic profiles. Live CAOSCare, Home Assistant, residents and production were untouched.

## Built

- A reusable `/api/dot-aria/*` backend surface authenticated by a dedicated token hash, exact Home Assistant source IP, existing owner role and one configured profile ID.
- Six Home Assistant response-returning scripts documented in `README.md`.
- Canonical request routing, content-aware deduplication, one receipt per delivery, exact request-ID status lookup and resident-safe response filtering.
- Fail-closed inputs: no tool accepts a resident name, room or resident ID; unknown fields are rejected.
- Explicit HA timeout/unavailable results. A script acknowledgment is not treated as a successful CAOSCare operation.
- Review-only package, environment template, read-only health check, rollback and acceptance procedure.

## Six exposed entities after activation

1. `script.caoscare_get_my_profile` — no input; the one configured approved test profile.
2. `script.caoscare_get_departments` — no input; active non-emergency routing labels/slugs.
3. `script.caoscare_get_menu` — optional ISO date and meal period; approved menu rows.
4. `script.caoscare_get_schedule` — optional ISO date; published activities/community services.
5. `script.caoscare_make_request` — stable operation ID, category, summary and priority; returns task/request ID, receipt ID, lifecycle status, duplicate/replay flags and delivery evidence. It does not claim service completion.
6. `script.caoscare_check_request_status` — exact returned `request_id`; returns the same request's safe open or closed state.

Only these six script entities are to be exposed to Assist. Never expose the underlying `rest_command.*` entities or any additional CAOSCare entity as part of this activation.

## Morning activation — owner-required

1. Review `README.md`, the six entity descriptions, and the real privacy expansion. Choose one existing **test** resident profile in CAOSCare and record its exact internal `resident_id`. A spoken name or room must not be used as authorization.
2. With no active call, have the authorized `caoscare-1` checkout owner bring this private commit into the coordinator-owned integration checkout using the normal reviewed handoff. Do not copy over that checkout or change account permissions. Keep the prior integration commit as rollback.
3. Create the dedicated credential locally only when activating. Use a terminal with `umask 077`; generate at least 32 random bytes into a mode-0600 file without printing it. Put only its SHA-256 hex digest in `backend/.env` as `CAOSCARE_DOT_ARIA_TOKEN_SHA256`. Add the existing Michael owner ID, the exact approved test profile ID and the verified HA VM IP using the four names in `caoscare-dot-aria.env.example`. Never paste the raw token into chat, logs, Git, or a command-line argument.
4. In Home Assistant's local File Editor/terminal, add the raw token once to `secrets.yaml` as `caoscare_dot_aria_authorization: "Bearer <local value>"`. The secret must stay in HA's local secret store. Remove the temporary raw-token file after both sides are configured.
5. Copy `caoscare_dot_aria_package.yaml.example` into the existing HA packages configuration. Run Home Assistant's configuration check. A HA restart is required to load new `rest_command` definitions; expect the existing HA MCP connection to reconnect. This was deliberately not done overnight.
6. Load the reviewed CAOSCare backend with the existing guarded dev procedure only while there is no active call or recent call activity. Verify `/api/health`, then run `health_check.sh`; enter the token at its hidden prompt. All four reads must return HTTP success and the selected test profile must be exact.
7. In Home Assistant **Settings → Voice assistants → Expose**, expose exactly the six `script.caoscare_*` entities listed above. Leave the REST commands and all other new entities unexposed.
8. Verify through Arya that the six tool names appear. This proves discovery only; it does not prove live reads or writes.

The route is default-off until steps 2–7 are completed. Home Assistant's MCP OAuth grant may cover more than these entities; the entity exposure list controls what its assistant offers. The CAOSCare channel token itself reaches only `/api/dot-aria/*` and one configured profile.

## Final test evidence

- Focused canonical gate: **10 passed, 1,517 deselected, 2 warnings** in 7.84 seconds. This covers normal reads and writes, source/credential/owner denial, profile isolation, invalid input, unavailable configured profile, duplicate delivery, receipt creation, and exact open/closed status lookup.
- Home Assistant package contract: parsed successfully as exactly six REST commands and six scripts; the health script passes `bash -n`. Static tests verify all six commands use the secret reference and 10-second timeout, while every script returns explicit transport and HTTP evidence instead of treating action acceptance as success.
- Final full canonical backend gate: **1,472 passed, 11 failed, 31 skipped, 13 deselected, 7 warnings** in 673.20 seconds.
- Exact failure comparison on the detached unchanged base `bc79f9eb0dbe02735e2d9b5d7b49994e1a96f01c`, using the same gate environment and the matching failing test files: **11 failed, 1,506 deselected, 2 warnings** in 344.82 seconds. The same tests failed: two `test_ops_metrics` assertions (expected 5, observed 4), eight `test_restart_dev_backend` cases (the shared `/tmp/restart_dev_backend.candidate.log` is owned by `caoscare-1` and is not writable by `michaelos`), and `test_therapy_recurrence::test_weekly_therapy_series` (the expected upcoming row is absent). No permissions were changed and no baseline file was edited.

The full suite is therefore not called green. The eleven failures are reproduced unchanged on the exact base and are not regressions from this channel. The new channel's focused tests are green.

## One supervised acceptance

Use the selected test profile and one clearly labeled test request. Do not use another resident.

1. Say: “What is for dinner today?” Verify Arya uses `caoscare_get_menu` and speaks only returned approved rows.
2. Say: “Ask maintenance to check the **test lamp** for my test profile.” Verify exactly one `caoscare_make_request` delivery. Capture its `request_id`, `receipt_id`, `status`, duplicate flag and delivery evidence. Arya must say it was filed/pending, never that maintenance completed it or is on the way.
3. Say: “Check the status of that exact request.” Verify `caoscare_check_request_status` is called with the same `request_id`, and its returned `task_id`/state match the created request.
4. Distinguish two cases: retry the same operation ID and payload to get the original task/receipt with no new notification or repeat count; make a genuine repeat ask with a new operation ID to follow the existing repeat-request policy. Different issues in the same department must remain distinct.
5. Use the current regular ChatGPT conversation's natural goodbye, then verify idle and another wake without reopening or reapproving. Do not send an old Home Assistant End event. This continuity check is separate from CAOSCare request acceptance.

Arya is not connected to CAOSCare until steps 1–3 pass live. A tool invocation, HA `action_done`, HTTP 200, or request receipt alone does not prove the service itself was completed.

## Health and rollback

Healthy means: existing wake and call path still ready; `/api/health` succeeds; read-only `health_check.sh` returns capabilities, the exact configured profile, departments and menu; a request returns both IDs; exact-ID status retrieves it.

Rollback:

1. Unexpose the six scripts from Assist.
2. Remove the four `CAOSCARE_DOT_ARIA_*` entries from `backend/.env` and guarded-restart only the dev backend. The routes then return 503.
3. Remove the HA package and `caoscare_dot_aria_authorization`, configuration-check and restart HA.
4. Return the CAOSCare checkout/runtime to the recorded prior integration commit if code rollback is needed.
5. Keep canonical task and receipt history; rollback does not erase evidence.

Rollback does not modify the Playwright extension, wake listener, EMEET route, Start/Hang-up helper or browser consent.

## Known limits and resume point

- No live HA package parse, restart, exposure, credential authentication or Arya call was performed. Those need Michael.
- Correction: missing HA/helper receipts do not prove a missed assistant invocation. Owner evidence includes actual tool invocations followed by network errors. The current regular ChatGPT Voice goodbye path is separate; do not replay earlier End requests.
- During this work, the live call helper entered its documented uncertainty lock after a Playwright `driver:connection` error. Read-only probes showed idle; the documented verified-idle reset restored `listening` without restarting either service. Persistence after browser restart/logout remains unproven and requires normal browser approval.
- Resume at activation step 1. Do not rebuild a messaging bridge, add a second microphone consumer, create a second CAOSCare business-logic path, or touch Linode/production.
