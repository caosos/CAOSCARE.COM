# Pilot 1 — Communications and calling (Lane F)

Owner: Lane F (`pilot/communications`). Status as of 2026-09-27.
Tracker: `docs/PILOT1_EXECUTION_CHECKLIST.md` Phases 4 and 6. This file
separates **configuration/runtime gaps** (need accounts, keys, DNS, hardware
or a decision) from **code gaps** (need engineering), and records the Pilot 1 phone architecture Michael
decided on 2026-09-27. It does not mark anything done.

---

## 1. Email and notifications

### Current path (code, verified by reading source and tests)

```text
Outbound:  resident_requests / tasks / transportation*
           → notifications.notify_department(slug, …)      routing: who
           → notification_delivery.send_email / send_sms    delivery: one record per attempt
           → db.notifications  (status + provider_message_id)
           ← Resend webhook email.delivered/bounced/… → apply_resend_delivery_event

Inbound:   Resend → POST /api/email/inbound/resend (Svix-signed)
           → email.received: allowlist per lane → menu_ingest / schedule_ingest
           → other email.* events: delivery status of an outbound notification
           → db.inbound_emails + receipt per outcome
```

Admin surface: **Admin → Communication & requests → Email & notifications**
(`CommunicationsTab.jsx`, `EmailInboundPanel.jsx`): provider status, test
send, delivery log filterable by status, approved inbound senders per lane,
inbound email provenance. Department inbox addresses are set on
**Departments** (`contact_email`).

### Delivery status vocabulary (models.py `NotificationStatus`)

| Status | Claim it makes |
|---|---|
| `logged` | No provider configured. Recorded only; nothing left CAOSCare. |
| `failed` | Provider rejected it, the call errored, or no recipient existed. |
| `sent` | Provider **accepted** it. Not proof of arrival. |
| `delayed` / `bounced` / `complained` / `delivered` | Reported later by Resend's webhook. Only `delivered` claims arrival. A late weaker event never overwrites a terminal one. |

### Department routing and fallback (`notify_department`)

1. `Department.contact_email` (shared department inbox)
2. staff `User`s with that department
3. admin/owner

A tier is skipped when it has no address **or every send in it failed at the
provider**. `logged` does not fall through (it would be logged identically at
every tier). No reachable address anywhere → one explicit `failed` record.
Returns the records so a caller can attach them to the request.

Front desk / admin requests route to `administration`
(`resident_requests.CATEGORY_ALIASES`: `front_desk`, `complaint`).

### Code gaps closed in this lane (commit on `pilot/communications`)

- Delivery truth: `sent` was the only success value and was claimed at
  provider acceptance; now `provider_message_id` is stored and Resend delivery
  events move a notification to `delivered`/`bounced`/`delayed`/`complained`.
- Bug: a Resend webhook subscribed to delivery events would have ingested
  `email.delivered` etc. as **inbound mail**. Non-`email.received` events are
  now routed to delivery status and never create an `InboundEmailMessage`.
- Fallback only triggered on "no recipients", not on provider failure; staff
  with no email address blocked the admin fallback; a department with nobody
  reachable produced no record at all. All three fixed.
- `notify_department` returned nothing; records now carry `department`,
  `route`, `related_object_type/id` and are returned.
- Leaked `httpx.AsyncClient` per send/fetch; provider keys read once at import.
- No admin UI for allowlists or inbound provenance; provider status and log
  were buried in the Family tab. Moved to one Communications tab.

### Code gaps remaining

| Gap | Owner | Notes |
|---|---|---|
| Callers do not pass `related_object_type="task", related_object_id=task_id` to `notify_department`, so delivery is not visible **per request** | Lane E (SC-3) + Lane C for transportation | One keyword argument per call site: `resident_requests.py` ×2, `transportation.py` ×3, `transportation_assign.py` ×1. Then `RequestHistoryDialog` can read `GET /notifications?related_object_id=`. |
| `tasks.py::_notify_department` is dead duplicate routing logic | Lane E (SC-3) | Never called; delete. |
| ~~Three separate Twilio code paths~~ — CLOSED (RQ-027) | Lane F | One path: `notification_delivery` (`send_sms`, `place_call`, `notify_alert_phone`) over httpx, no `twilio` package. `TWILIO_FROM_NUMBER` is the name; `TWILIO_FROM_PHONE` is accepted as an alias. Escalation SMS (level 2 supervisor / level 3 on-call) and the live-line on-call call each write a linked `db.notifications` record and an appended receipt; no provider = `logged`; simulated work = `simulated`, never sent. |
| Inbound lanes are only `menu`, `activities` | Lane F + Lane D | Adding a department address = one entry in `email_inbound._RECIPIENT_LANES` + `EmailAllowlistLane`. Not needed for Pilot 1 unless Michael names one. |
| Delivery events for mail sent by a node that is not publicly reachable | Runtime/topology | Resend delivers webhooks to one public URL. Mail sent by the EliteDesk backend cannot receive its own delivery events unless that URL reaches it. See §3. |

### Configuration / runtime gaps (no code change needed)

Presence of `RESEND_*`/`TWILIO_*` in the running EliteDesk backend was not
checked (credential inspection is not permitted to this lane); the
integration `backend/.env` contains none of them. Production was not checked.

1. **Resend sending domain** — verify a domain (e.g. `caoscare.com` or a
   facility domain) and set `RESEND_FROM_EMAIL` on it. The default
   `onboarding@resend.dev` can only send to the Resend account owner's
   address, so real department notifications fail until this is done.
2. **`RESEND_API_KEY`** in the backend environment of whichever backend
   creates the requests (and of the backend receiving inbound mail — it
   fetches the body from Resend's receiving API).
3. **Inbound receiving** — enable receiving on a domain/subdomain (MX), e.g.
   `inbound.caoscare.com`, so `menu@…` and `activities@…` resolve.
4. **Webhook** — one Resend webhook to
   `https://<public backend>/api/email/inbound/resend`, subscribed to
   `email.received` and `email.delivered`, `email.delivery_delayed`,
   `email.bounced`, `email.complained`, `email.failed`, `email.suppressed`.
   Put its `whsec_…` signing secret in `RESEND_WEBHOOK_SECRET`. Without it the
   endpoint returns 503 (fails closed).
5. **Department addresses** — set `contact_email` for nursing, maintenance,
   transportation and administration (front desk) in Admin → Departments, or
   give staff users their department and email.
6. **Allowlists** — approve the kitchen sender for `menu` and the activities
   sender for `activities` in Admin → Email & notifications.
7. **Twilio SMS** (optional for Pilot 1 email scope) — `TWILIO_ACCOUNT_SID`,
   `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`.

### Acceptance tests to run once configured (none run yet)

| Checklist item | Test | Evidence to record |
|---|---|---|
| Real inbound menu email | Approved sender emails `menu@<domain>` with a `Date: YYYY-MM-DD` line | `inbound_emails` row `routed`, `menu_uploads` row, review/publish in Menu tab |
| Real inbound activities email | Approved sender emails `activities@<domain>` with day headers | `inbound_emails` `routed`, `schedule_items` with `source_ref` |
| Sender allowlist | Unapproved sender to `menu@` | `quarantined`, no upload |
| Nursing / maintenance / transportation / front desk notification | Real request per category from the kiosk or front desk | `notifications` row per department with `status` `sent` then `delivered` |
| Delivery/receipt visibility | Same rows in Email & notifications | status + provider event shown |
| Fallback routing | Department with no contact and no staff; then an invalid contact address | `admin_fallback` record; failed contact followed by next tier |

---

## 2. Calling — Pilot 1 architecture (decided 2026-09-27)

Michael's decisions D1–D8 are recorded below with how each is implemented.
**Nothing here has run against real hardware, Asterisk, a SIP trunk or
OpenAI.** Asterisk is not installed on the EliteDesk (Ubuntu candidate:
Asterisk 18.10). Config files are in `telephony/asterisk/`.

| # | Decision | Implementation |
|---|---|---|
| D1 | Asterisk | `telephony/asterisk/` for Asterisk 18 (PJSIP, ARI, func_curl) |
| D2 | Analog handset + ATA, off-hook reaches Aria with no digits | ATA **warm line** (see §2.3) |
| D3 | SIP trunk, provider compared first | §2.8 — recommend Telnyx credential trunk |
| D4 | Handset: Aria transfers; eMeet: Aria asks resident to pick up | §2.4 |
| D5 | Real SIP desk phone on local Asterisk | extension 200 |
| D6 | 911 bypasses Aria completely | §2.6 |
| D7 | Phone control and call-state truth local | Asterisk + EliteDesk backend; ARI is local; Linode not involved |
| D8 | Current OpenAI Realtime SIP, verified | §2.2 |

### 2.1 Topology

```text
analog handset ─RJ11─ ATA (FXS)  ──SIP/LAN──┐
front desk SIP phone (ext 200) ──SIP/LAN────┤
                                            ▼
                       Asterisk 18 on the EliteDesk
             [from-room]   0 → 200 · 911/9911 → trunk · 700 → OpenAI
             [caos-transfer]  REFER target 77<token> → CURL CAOSCare → Dial
             ARI (127.0.0.1:8088) ──events──► CAOSCare backend (same host)
                       │                          call_sessions + receipts
          TLS 5061/SRTP│ trunk "openai"           ▲
                       ▼                          │ realtime.call.incoming
              OpenAI Realtime SIP ────────────────┘ (webhook, via tunnel)
                       │ sideband WebSocket (outbound from backend)
          SIP trunk ───┴── PSTN (family calls, 911 with E911 address)
```

Extensions (Pilot 1):

| Ext | What | Where defined |
|---|---|---|
| `2XX` (e.g. 214) | Room handset, one per ATA port; ext = room number where possible | `pjsip_local.conf`, and Admin → Phones & calls (kind *Room handset*, room) |
| `200` | Front desk SIP phone | same, kind *Front desk* |
| `700` | Aria (OpenAI SIP) | dialplan only; optionally listed as kind *Aria* |
| `0` | Dials 200 from a room | dialplan |
| `911`, `9911`, `933` | Emergency / provider address test | dialplan, trunk only |

### 2.2 Aria on the handset (verified against OpenAI's SIP guide, 2026-09-27)

1. Off-hook → ATA warm line dials 700. Dialplan sets `CAOS_CALL_ID=aria-<uniqueid>` and dials `sip:<OPENAI_PROJECT_ID>@sip.api.openai.com;transport=tls` with headers `X-CAOS-Call-Id` and `X-CAOS-Extension`.
2. OpenAI POSTs `realtime.call.incoming` (Standard Webhooks signature, `OPENAI_WEBHOOK_SECRET`) to `/api/telephony/openai/webhook` (`routes/phone_aria.py`). The backend maps extension → room → resident, then `POST /v1/realtime/calls/{call_id}/accept` with `type: realtime`, `model: OPENAI_REALTIME_MODEL` (existing env; the guide's example uses `gpt-realtime-2.1`; the code default is `gpt-realtime` — set the env var, do not hard-code), the resident's normal companion instructions plus a telephone section.
3. `routes/phone_aria_sideband.py` opens `wss://api.openai.com/v1/realtime?call_id=…`, installs the phone tools, near-field noise reduction and `gpt-4o-transcribe`, and saves each turn through the same `realtime_turn_ingest` the room uses (so request grounding and memory work unchanged).
4. Phone tools (`routes/phone_aria_tools.py`): `request_staff_help`, `check_request_status`, `transfer_to_front_desk`, `call_family_contact`, `end_call`. They call the same backend functions as the room tools. `end_call` hangs up only if the resident's last words are a goodbye (same phrase set as the room path's guard).
5. If OpenAI or CAOSCare cannot be reached, the dialplan falls back to ringing the front desk. A signed webhook for an unknown call is rejected.

Not on the phone path: lights/TV/thermostat (room voice only).

### 2.3 ATA warm line (D2 + D6 together)

A pure *hotline* (dial the instant the handset lifts) would make 0 and 911
impossible to dial from that phone. Use a **warm line**: off-hook, wait
about 3 seconds for a digit, then auto-dial 700. A resident who just picks up
and waits reaches Aria without dialing; a resident who dials 911 or 0 is
routed immediately.

ATA settings (field names differ by model — confirm on the purchased unit):
- Off-hook auto-dial: `700`; auto-dial delay: `3` s
- Dial plan: send `0`, `911`, `9911`, `933` immediately, no inter-digit wait
- SIP account = the room extension/password from `pjsip_local.conf`; DTMF RFC 2833/4733; G.711 µ-law
- Registration to the EliteDesk's LAN address

### 2.4 "Call the front desk" (D4, D5)

- **On the handset:** Aria says she is connecting them, then (after she finishes speaking) the backend creates a `front_desk` CallSession with a one-time token and calls OpenAI `refer` with `sip:77<token>@…`. Asterisk puts the resident's leg in `[caos-transfer]`, CURLs `/api/telephony/local/dial-target/<token>` (localhost + `CAOS_TELEPHONY_TOKEN`, token valid 120 s, single use), and dials `PJSIP/200`. Unknown/expired token → rings the front desk anyway.
- **From the eMeet room session:** Aria asks the resident to pick up the handset. When they do, the warm line brings them to Aria on the phone, who transfers as above. No room-browser code change is needed for this; the eMeet-side wording is a Resident Aria prompt change (not made here — Aria lane).
- Dial 0 reaches 200 with no CAOSCare involvement.
- Unanswered front desk: the call is recorded `unanswered`; Pilot 1 has no voicemail/queue. See open items.

### 2.5 Approved family call

- Staff tick **Resident may call** on a family contact (Admin → Family; `PATCH /family-contacts/{id}/calls`, admin only; off by default; needs a phone number).
- Aria's `call_family_contact` tool only offers approved contacts' ids; names (never numbers) are in her instructions. The number comes from the stored contact, normalized to E.164 (NANP), and is resolved by Asterisk through the same one-time token, then dialed on the trunk with the room's DID as caller ID.
- Aria never takes a number from speech.

### 2.6 911 (D6)

- `911` and `9911` in `[from-room]`: set `CAOS_CALL_ID=emg-…`, set caller ID to the room's DID, start the front-desk alert in the background, `Dial(PJSIP/911@trunk)`. No CURL, no Aria, no wait before the Dial. If the trunk fails, ring the front desk.
- Front desk alert (`caos-911-alert.sh`): writes an Asterisk call file that rings ext 200 and reads out "911, room 214" — the on-site notification Kari's Law expects for multi-line systems. It is backgrounded so it cannot delay the emergency call.
- CAOSCare records the call afterwards from ARI and emails administration. That record can never affect the call.
- **Dispatchable location:** each pilot room needs its own DID with an E911 address that includes the room/apartment (RAY BAUM'S Act). Confirm the exact obligations with the provider and counsel before a handset goes in a room.
- Aria, if told of an emergency on the phone, tells the resident to hang up and dial 9 1 1 or press their pendant. The community pendant/call system remains authoritative and unchanged.

### 2.7 Call state and receipts (built)

`CallSession` (`backend/models_calls.py`, collection `call_sessions`):
`requested → dialing → ringing → connected | unanswered | failed → ended`.

- Sources: Asterisk ARI `Dial` events (`dialstatus` "" → dialing, RINGING/PROGRESS → ringing, ANSWER → connected, NOANSWER/BUSY → unanswered, CHANUNAVAIL/CONGESTION → failed, CANCEL → ended) and `ChannelDestroyed` → ended with cause (`routes/asterisk_ari_events.py`); OpenAI accept/refer failures → failed. Never Aria's words.
- Correlation: inherited channel variable `CAOS_CALL_ID`, listed in `ari.conf channelvars`. Dialplan-started calls (`aria-`, `fd0-`, `emg-`) are created on their first event.
- Forward-only transitions; late/duplicate events are ignored; each change is appended to `history` with time, source and detail.
- Receipts: one when the attempt is requested, one for the outcome (connected / unanswered / failed). New rows, never edits.
- `spoken_call_state()` gives the only wording Aria may use for a state ("ringing, nobody has answered yet").
- Admin → Communication & requests → **Phones & calls**: extensions and the call log with each state change.

### 2.8 SIP trunk provider (D3)

| | Telnyx (credential connection) | Twilio Elastic SIP Trunking | VoIP.ms |
|---|---|---|---|
| Works behind the EliteDesk NAT | Yes — registration; inbound arrives over the registration | Outbound with credentials; inbound needs a publicly reachable SIP address (port forward) | Yes — registration sub-account |
| Asterisk guide | Official credential-trunk guide | Official guides | Official wiki |
| E911 per number with suite/apartment | Yes, portal/API, dynamic E911 | Yes, per number (MSAG-validated), monthly fee | Yes, per DID |
| E911 test | Documented test procedure | — | — |

**Recommendation:** Telnyx credential connection — simplest behind NAT,
per-room DIDs each with an apartment-level E911 address, documented Asterisk
setup. Prices and current terms were not verified; compare before buying.
Twilio is fine if inbound calls to rooms are not needed in Pilot 1.

### 2.9 What is needed, by kind

**Code — built in this lane (tests only):** CallSession lifecycle + receipts;
ARI event mapping and listener; local dial-target endpoint; extension
registry; family call approval; OpenAI SIP webhook, accept and sideband tool
runner; Phones & calls admin tab; Asterisk config (`telephony/asterisk/`).

**Code — not built:**
- eMeet-session prompt wording "please pick up your phone" (Resident Aria lane).
- Unanswered front desk: queue, callback request or voicemail (needs Michael's choice).
- Syncing call receipts to Linode (D7 allows it; not needed for operation).
- Installing Asterisk as a boot-persistent service and a tunnel for the webhook (ops work on the EliteDesk).

**Hardware:**
- ATA with warm-line (off-hook auto-dial delay) support — one FXS port per pilot room (e.g. a 1–2 port model; confirm the setting exists before buying).
- Analog corded handset/phone with a simple, large-button base.
- SIP desk phone for the front desk (PoE or with power supply).
- Network: EliteDesk wired/stable LAN; router allows outbound TLS 5061 and UDP RTP to OpenAI's published ranges (SRTP must flow both ways — may need an RTP port-forward restricted to OpenAI's CIDRs).

**Accounts / provider setup:**
- SIP trunk account; one DID per pilot room (+ optionally a main DID); E911 address on each room DID including the room number; confirm 933 test support.
- OpenAI project: SIP enabled, project ID, webhook pointing at the tunnel URL for `/api/telephony/openai/webhook`, webhook signing secret.
- A tunnel (e.g. Cloudflare Tunnel) exposing only that webhook path of the EliteDesk backend over HTTPS.

**Secrets / configuration** (names only; never committed):

| Where | Variable | Purpose |
|---|---|---|
| backend env | `OPENAI_API_KEY` | already used; accept/refer/hangup + sideband |
| backend env | `OPENAI_WEBHOOK_SECRET` | verify `realtime.call.incoming` (webhook fails closed without it) |
| backend env | `OPENAI_REALTIME_MODEL` | e.g. `gpt-realtime-2.1` (existing variable) |
| backend env | `CAOS_TELEPHONY_TOKEN` | shared with the dialplan; dial-target fails closed without it |
| backend env | `CAOS_TELEPHONY_ALLOWED_HOSTS` | default `127.0.0.1,::1` |
| backend env | `ASTERISK_ARI_URL`, `ASTERISK_ARI_USER`, `ASTERISK_ARI_PASSWORD` | ARI listener (off when unset), e.g. `http://127.0.0.1:8088` |
| backend env | `CAOS_SIP_TRUNK_ENDPOINT` (default `trunk`), `CAOS_REFER_HOST`, `CAOS_PHONE_VOICE` | optional |
| `pjsip_local.conf` | room/front-desk passwords, `ROOM_DID` per room, trunk username/password/host, NAT addresses | Asterisk |
| `extensions_local.conf` | `FRONT_DESK_EXT`, `OPENAI_PROJECT_ID`, `CAOS_API`, `CAOS_TELEPHONY_TOKEN` | Asterisk |
| `ari_local.conf` | ARI user password | Asterisk |
| backend deps | `pip install -r requirements.txt` (adds `websockets>=14`) | listener + sideband |

### 2.10 Live acceptance tests still required (none run)

| Checklist item | Test | Evidence |
|---|---|---|
| Analog handset / ATA | ATA registered to Asterisk | `pjsip show endpoints` shows 214 Avail |
| Off-hook → Aria | Lift handset, wait | Aria greets by name within ~5 s; `call_sessions` aria-… `dialing → connected`; webhook accepted |
| Dial 0 → front desk | Lift, dial 0 | Desk phone rings; fd0-… `ringing → connected → ended`. Repeat unanswered → `unanswered` |
| Dial 0 with CAOSCare stopped | Stop backend, dial 0 | Desk phone still rings |
| "Aria, call the front desk" | On handset | REFER sent after Aria finishes; desk rings; child call `connected`; Aria never said "answered" |
| eMeet → handset | Ask Aria via eMeet | Aria asks resident to pick up; transfer from handset works |
| Approved family call | Approved contact | Rings the real number with the room DID; unapproved contact refused |
| Call states | Each of: answered, no answer, busy, bad number | Correct terminal state + receipts per call |
| 911 route | Provider's 933 test (not 911) from the room handset | Provider reads back the room's registered address; front desk alert rings |
| 911 independence | Stop backend and OpenAI access; dial 933 | Still routed; front desk alert still rings |
| 911 delay | Time from last digit to trunk INVITE | No added delay versus a plain Dial |
| No tablet required | Whole flow from the handset only | — |
