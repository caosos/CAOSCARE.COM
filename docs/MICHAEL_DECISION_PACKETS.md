# Michael decision packets — 2026-10-08

Companion to `docs/MICHAEL_ACTION_RUNBOOK.md` (that file has the exact commands; this one has the **questions**). Each packet: question · why it matters · recommended default · downside of the default · what it unblocks · can it wait. Reply with the packet number and `YES / NO / <option>`; the coordinator does the rest.

Facts used here were read from the repo on 2026-10-08. Anything needing production or hardware access is marked UNVERIFIED. Nothing below was acted on without your word.

**State change since the runbook was written:** the `:8092` backend is now **running on integration tip `2a2d569`** (started 2026-10-08 10:10 CDT after checking: the only lease row, room 214, was 19 h stale; no open non-stale alerts; no Twilio/Resend keys). Health ok; `/api/simulator/scenarios` 401; `/api/realtime/aria-session` 401; `by-kiosk` returns only 4 resident fields; localhost:3000 proxies to it. Runbook step 1 is therefore **done**.

---

## P1. Security B1 / B2 / A — built, awaiting your merge-and-release word
- **Question:** may the three remaining public-route fixes (B1 Aria read routes need admin sign-in; B2 interpretation-pattern confirm needs a live session and the resident's own words; A conversation-turn needs owner sign-in) go into the next release?
- **Why:** each lets anyone on the network read or write resident language data (`docs/reports/2026-10-06-security-followup-aria-public-routes.md`). They exist in production (`d7ff96a`) too.
- **Default:** YES. I treated these as coordinator-approvable, not owner-gated, and launched worker RQ-025 to build exactly the report's "smallest safe fix" (draft PR, gate). You only need to say when it ships (P9).
- **Downside:** a legitimate caller I did not find over HTTP would get 401/403. The worker is told to prove callers by grep first and test the kiosk path.
- **Unblocks:** closing the Pilot 1 security blockers; `/api/memory/realtime-turn` review.
- **Can wait?** Locally yes (LAN only); **not** once any real resident room is on a public host.

## P2. Public kiosk listing (`GET /api/kiosks`, plus `by-kiosk` name)
- **Question:** which option: (1) keep public but trim to `kiosk_id` + `room`; (2) the room screen fetches only its own kiosk record; (3) later, a per-kiosk device credential (`device_auth.py`)?
- **Why:** the list gives anyone the kiosk ids; `by-kiosk/{id}` (already trimmed in B3) still returns the resident's name and room for each id. After B1/B2 the id is no longer enough to read or write Aria data, but names remain enumerable.
- **Default:** option 1 now, option 3 before a real room is reachable from outside the community network.
- **Downside:** names + rooms stay readable by anyone who can reach the API. Fine on a closed LAN; not fine on the public internet.
- **Unblocks:** a precise fix PR (consumers of `/api/kiosks` must be checked first: UNVERIFIED which screens call it unauthenticated).
- **Can wait?** Yes while the pilot stays on the local network; no for a public deployment with residents.

## P3. Email / RQ-005
- **Question:** which sending domain and who owns inbound mail?
- **Why:** code is done and tested (`notification_delivery.py`, Resend webhook, allowlists, per-department fallback); nothing real has been configured (`docs/PILOT1_COMMUNICATIONS.md` §1). Resend delivers webhooks to **one public URL**, and the EliteDesk is not public.
- **Default:** verify `caoscare.com` in Resend (DNS at GoDaddy), receive on `inbound.caoscare.com`, point the webhook at the **Linode** backend, and treat Linode as the owner of inbound menu/activities mail; the EliteDesk sends outbound notifications with the same key. Put real department `contact_email`s in Admin → Departments and approve the kitchen/activities senders.
- **Downside:** menu/activities mail lands on the Linode DB, not the EliteDesk pilot DB (the local-first pilot would not see it without a sync); delivery events for EliteDesk-sent mail cannot return to the EliteDesk.
- **Unblocks:** checklist Phase 4 (about 14 boxes) and RQ-005 acceptance.
- **Needs from you:** Resend API key (you paste it into the server `.env` yourself), DNS access, the real department addresses, the kitchen and activities sender addresses.
- **Can wait?** Yes for the demo; **no** for any claim that staff are really notified.

## P4. Telephony / Asterisk / SIP / ATA
- **Question:** go or no-go on the Pilot 1 phone path, and four answers: SIP trunk provider, ATA model, unanswered-front-desk behaviour, 911 position.
- **Why:** config, dialplan, call-state receipts and the Aria SIP bridge are written but have never run (`telephony/asterisk/README.md`, `PILOT1_COMMUNICATIONS.md` §2). Asterisk is not installed (needs `sudo`).
- **Default:** (a) defer calling out of the first resident room demo if hardware has not arrived; (b) when ready, install Asterisk on the EliteDesk, one analog handset on one ATA, a registered-trunk provider that works behind the EliteDesk's NAT (the §2.8 table), unanswered front desk → callback request (a StaffTask, so it is already receipted); (c) 911: not enabled until counsel confirms dispatchable-location obligations (§2.6).
- **Downside:** no resident-to-front-desk call in the pilot until step (b) is done; the callback fallback is slower than a live answer.
- **Unblocks:** Phase 6 (about 17 boxes), RQ-006.
- **Needs from you:** provider choice and account, ATA/handset/desk-phone purchases (authority is yours; I buy nothing), a wired port and sudo window on the EliteDesk.
- **Can wait?** Yes, but it is the longest lead-time item; start the hardware and account steps early.
- **Autonomous side:** consolidating the three Twilio code paths (one imports a package that is not in `requirements.txt`) is code-only and is queued as RQ-027.

## P5. Storage cleanup / RQ-008 Phase 2
- **Question:** which item ids may be deleted?
- **Why:** 56 GB free, 75 % used; wake/firmware data is about 71 GB of it (`docs/reports/2026-10-04-elitedesk-storage-audit.md`).
- **Default:** approve S1–S3 (safe after the wake test, about 1.9 G); everything wake/firmware (A–F) waits for Claude Two's say-so; H (RF bridge log) is moot, say `H: drop`.
- **Downside:** deletions are not recoverable except what each item says it can regenerate.
- **Unblocks:** disk headroom for builds and lab runs. Not a Pilot 1 gate.
- **Can wait?** Yes until free space drops under about 30 GB.

## P6. Home Assistant host protections (`docs/HA_VM_RECOVERY.md`)
- **Question:** install P1 (oom_score_adj hook for the VM's qemu), P2 (root timer that starts the VM only when it is "shut off (crashed)"), P3 (memory caps for heavy builds)? And is the 2026-10-07 reboot proof enough (6a)?
- **Why:** the VM died in a host OOM on 2026-10-03 and stayed off until a human started it; autostart does not cover that.
- **Default:** 6a NO (accept 10-07 as proof); P1 YES, P2 YES, P3 YES. Worker RQ-026 writes the exact files under `docs/ops/ha-vm/` for your review; nothing installs until you run the documented steps with `sudo`.
- **Downside:** P1 makes the host's other processes likelier OOM victims; P2 is a root timer to maintain.
- **Unblocks:** "VM recovers after OOM without SSH" (Phase 7/8 criterion).
- **Can wait?** Yes for the demo; no for a room that must run unattended.

## P7. Agent sessions / demo continuity / PR #67
- **Question:** (a) adopt the persistent `caos-agent-01..06` tmux sessions of PR #67? (b) turn `CAOSCARE_DEMO_CONTINUITY_AUTO` on for the EliteDesk? (c) lift the demo-room-only limit on the simulator and continuity?
- **Why:** (a) contradicts the "fresh bounded workers, max two" rule your coordinator instruction sets; #67's code was fixed to my review and CI is green. (b) keeps the DEMO room believable after time passes. (c) is gated by ENGINEERING_CONTRACT items 7 (legacy data policy) and 8 (done: RQ-018).
- **Default:** (a) decline persistent sessions; merge only the Agent Operations UI/API if you want it, behind its disabled-by-default flag (say `review only`); (b) ON for the EliteDesk only, after you finish or stop run `simrun_4b9a3f2c415d`; (c) NO.
- **Downside:** (a) no always-on foreman; (b) one more background write path on a shared DB (limited to room `DEMO`, receipted); (c) none.
- **Unblocks:** (a) closes RQ-010; (b) a self-refreshing demo; (c) simulating real rooms later.
- **Can wait?** All yes.

## P8. Legacy data: 300+ stale active alerts
- **Question:** may the old RF-test alerts (status `active`, older than 72 h, from 2026-08/09 hardware testing) be closed in bulk with a receipt, or stay as is?
- **Why:** they are excluded from counts and from escalation (RQ-018 skips >72 h), so nothing is harmed, but the Alerts board still lists them as "likely stale".
- **Default:** leave them (preserve evidence), revisit when you want a clean board.
- **Downside:** clutter; a bulk close would rewrite history unless done as a labelled, receipted legacy-quarantine action.
- **Can wait?** Yes.

## P9. Release sequence (Linode)
- **Question:** approve the release path? Nothing deploys without it.
- **Why:** production is `d7ff96a`; `origin/main` is `880d10f`; integration is 199+ commits ahead of main; `scripts/deploy_caoscare.sh` refuses commits that are not in `origin/main` (UNVERIFIED on the server today).
- **Default sequence:** (1) merge RQ-025 (security) and finish the live nursing test (P10); (2) RQ-026 produces `docs/RELEASE_READINESS_2026-10-08.md` (merge conflicts, new env vars, indexes, startup side effects, smoke tests); (3) you approve a merge of integration into `main` as a reviewed PR; (4) you paste the RELEASE APPROVAL block from the runbook with the exact SHA; (5) deploy; (6) run `setup_demo_room.py` on production if you want the DEMO room there.
- **Downside:** 223 commits in one release including database-affecting code; the mitigation is the script's Mongo backup and the documented rollback.
- **Unblocks:** B3 and every fix reaching caoscare.com.
- **Can wait?** Yes, but production keeps the B3/B1/B2/A exposures until it ships.

## P10. Live acceptance only you can do
- **RQ-003 nursing voice test** (runbook §2): now unblocked, `:8092` is up. Use the DEMO room only. Takes about 15 minutes.
- **Pilot hardware facts** (runbook §3): Room 1, TV, thermostat, plugs, Voice PE arrival, wall plates, network answers.
- **Real drivers, vehicles, hours** (runbook §4). **Also decide:** link a transport driver to a staff user account (nullable `user_id` on the driver, chosen by an admin) so a driver sees "My tasks today". Default YES; downside: one new optional field; nothing breaks if it is empty.

## P11. Smaller closes
| # | Question | Default |
|---|---|---|
| a | Okay-Nabu test stack (listener :8766, backend :8096) | Not running today (checked); close it |
| b | PRs #41/#42 (public site, base `main`) and #23 (voice tempo, base `main`) | Review separately after the Pilot release; do not mix into integration |
| c | Phase 12 blue/white visual system | Defer until after Pilot 1 acceptance |
| d | RQ-002 Global Ask Aria governance (same Aria, page-aware, permission-scoped) | Approve in principle after P1; a worker can start once B1/B2 are merged |
| e | `pilot/shared-core-rerequest`, `docs/care-app-audit-2026-10-03`, PR #45 | Archive (close) unless you want specific items |
| f | Voice PE flashing | Wait for arrival; the package is on PR #46 and says do not flash |

## P12. Research + model A/B approvals (consolidated, 2026-10-09)
See `docs/OWNER_APPROVALS_RESEARCH_AND_AB.md`: one table (A model choice, B one smoke call, C live research switch, D model A/B, E Room 214 voice model) and one paste-ready approval line. Everything is built and tested offline; nothing paid or enabled.
