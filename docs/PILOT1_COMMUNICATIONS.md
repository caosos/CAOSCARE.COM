# Pilot 1 — Communications and calling (Lane F)

Owner: Lane F (`pilot/communications`). Status as of 2026-09-27.
Tracker: `docs/PILOT1_EXECUTION_CHECKLIST.md` Phases 4 and 6. This file
separates **configuration/runtime gaps** (need accounts, keys, DNS, hardware
or a decision) from **code gaps** (need engineering), and proposes the Pilot 1
phone architecture for Michael's decision. It does not mark anything done.

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
| Three separate Twilio code paths with different env names | Lane F (with calling) | `notification_delivery.send_sms` uses `TWILIO_FROM_NUMBER`; `escalation.py::_try_sms` and `resident_activation.py::try_call_on_call_phone` use `TWILIO_FROM_PHONE` and the `twilio` package, which is **not in requirements.txt** — both fail at import even with keys. Consolidate onto `notification_delivery` when calling is built. |
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

## 2. Calling — proposed Pilot 1 architecture (decision required)

### What exists today

- No call model, no call lifecycle, no SIP/PBX code. The only calling code is
  `resident_activation.try_call_on_call_phone`: a one-way Twilio TwiML
  `<Say>` announcement to the facility on-call phone. It is not a two-way
  call and currently cannot run (no `twilio` package).
- `FamilyContact` has `phone`, but no permission saying the resident may
  **call** that contact (only `notify_on` for alerts).
- Resident Aria runs in the room-node browser over WebRTC; tools execute in
  the browser and call backend endpoints.

### Proposed topology

```text
analog handset ──RJ11── ATA (FXS port, one per room)
                          │ SIP (LAN)
                          ▼
                 Asterisk PBX on the facility/room node (local-first)
                   ext 1xx  = room handsets (ATA port ↔ room ↔ resident)
                   ext 700  = Aria
                   ext 0    = front desk (desk SIP phone or ring group)
                   trunk A  = SIP trunk provider → PSTN (family, outside)
                   trunk B  = OpenAI Realtime SIP (TLS 5061 + SRTP)
                          │
                          │ ARI events (dial, ringing, answer, busy, hangup)
                          ▼
                 CAOSCare backend: CallSession lifecycle + receipts
```

| Behaviour | How it works |
|---|---|
| Off-hook → Aria | ATA hotline (auto-dial on off-hook) to ext 700. Asterisk sends the call to OpenAI SIP. The backend receives `realtime.call.incoming`, maps the calling extension to room/resident, accepts it with the same instructions builder as the room session (`_build_companion_instructions`), and runs a small server-side tool set over the sideband WebSocket (`wss://api.openai.com/v1/realtime?call_id=…`). Hang up ends the call. |
| Dial 0 → front desk | ATA dial plan sends `0` to ext 0; handled entirely in Asterisk. Aria is not involved. |
| "Aria, call the front desk" | On the handset: Aria's `call_front_desk` tool → `POST /v1/realtime/calls/{id}/refer` → SIP REFER → Asterisk transfers the handset to ext 0. From the eMeet room session: needs decision D4. |
| Approved family call | `call_family_contact(contact_id)` only for contacts marked callable for that resident; number comes from the record, never from speech. REFER to trunk A. |
| Truthful lifecycle | `CallSession` states set only from ARI/OpenAI events: `requested → dialing → ringing → connected \| unanswered \| busy \| failed → ended`. Aria reads the state; she never says "connected" or "they answered" without an `answer` event. One receipt per external effect. |

Why this shape: the handset keeps the resident's familiar interaction; the
PBX owns all telephony (dial 0 works even if CAOSCare is down); Aria is one
extension, not a second phone system; call state comes from the telephony
layer, not the model.

### Code that would be built after approval (Lane F)

1. `CallSession` model/collection + receipts (lifecycle above) and an ARI
   event consumer. Coordinate the shared receipt semantics with Lane E
   (receipts append per effect — SC-1).
2. Room ↔ extension mapping (extend `Kiosk`/room configuration — Lane E if
   it touches shared room records).
3. `FamilyContact.allow_calls` (per-resident approval) + admin toggle.
4. OpenAI SIP webhook handler + sideband tool runner with Pilot tools only:
   `request_staff_help`, `check_request_status`, `call_front_desk`,
   `call_family_contact`, `end_call`. These call the same backend service
   functions as the browser tools; browser-side grounding guards that exist
   only in JS must be ported, not skipped.
5. Consolidate the Twilio paths (§1) onto one module.

### Decisions needed from Michael

| # | Decision | Why it blocks |
|---|---|---|
| D1 | PBX: Asterisk (recommended; FreePBX UI optional) and which host — the room EliteDesk or a separate facility node | Everything else registers to it |
| D2 | ATA model (e.g. a 1–2 port FXS ATA with hotline/off-hook auto-dial and TLS) and handset | Hardware purchase; must support off-hook auto-dial |
| D3 | SIP trunk provider and numbers (family/outside calls, caller ID) | Outbound PSTN |
| D4 | "Aria, call the front desk" from the eMeet session: (a) Aria asks the resident to pick up the handset, (b) a softphone on the room node uses the eMeet for the call | Two different builds |
| D5 | Front desk endpoint: a desk SIP phone on the PBX, or forward to the facility's existing front-desk number | Where ext 0 rings; unanswered behaviour (queue/callback) |
| D6 | **911 / emergency dialing from the handset.** Residents may dial 911 on any phone. Either pass 911 straight to a trunk with a registered E911 address (independent of Aria/CAOSCare, which only records it) or ensure the device cannot be mistaken for a working phone. CAOSCare must not become emergency dispatch. | Safety/legal; must be settled before a handset is placed in a room |
| D7 | Public reachability: OpenAI's `realtime.call.incoming` webhook (and Resend's) must reach a public HTTPS URL, but Room 214's resident data lives in the EliteDesk database, not Linode | Which backend owns calls for a pilot room; tunnel vs production |
| D8 | Aria engine for phone calls: OpenAI Realtime SIP (above) vs the pending `gpt-live-1` decision | Same bridge either way at the PBX; differs in the backend handler |

Until D1–D3 and D6 are decided nothing in §2 is built; the checklist item
"Finalize Pilot 1 phone architecture" stays `[ ]` until Michael approves.
