# Pilot 1 email dependencies

Created: 2026-10-01, for ready-queue item RQ-005 (Live email / Resend acceptance, BLOCKED).
Based on: `integration/2026-09-27` @ `c8c61d1`, `pilot/communications` @ `0978bb1`, production `d7ff96a`.
Read from source only; no environment, Resend account or DNS was inspected.

The technical reference is Lane F's `docs/PILOT1_COMMUNICATIONS.md` §1 (on `pilot/communications`, not yet integrated). This file is the short list of what Michael must provide, plus the code gaps that are not his.

## Current state

| Part | State |
|---|---|
| Inbound webhook `POST /api/email/inbound/resend` (signature check, dedupe, sender allowlist, menu/activities routing) | Built; on integration and in production (`d7ff96a`, commit `e092e36`) |
| Sending (`send_email` via Resend) | Built; with no key every email is stored as `logged`, never sent |
| Truthful delivery status (`sent` → `delivered` / `bounced` / …) from Resend events | Built on `pilot/communications` only; not integrated, not deployed |
| Department notice routing with fallback (department inbox → department staff → admin/owner) | Fallback version on `pilot/communications` only; production sends only to `Department.contact_email` |
| Resend account, keys, domains, webhook, allowlists, department addresses | Not done |
| Expected-information lifecycle and reminder emails | Not built anywhere |

## What Michael needs to do

Secrets go straight into the server's `backend/.env`, never into chat or git.

- [ ] **1. Resend account and API key.** Confirm the account. Create a key that can send and receive. Set `RESEND_API_KEY`.
- [ ] **2. Sending domain.** Verify `caoscare.com` (or a subdomain such as `send.caoscare.com`) in Resend. Add Resend's SPF and DKIM records at GoDaddy; a DMARC record is recommended. Choose the from-address (for example `aria@caoscare.com`) and set `RESEND_FROM_EMAIL`. The default `onboarding@resend.dev` can only send to the Resend account owner.
- [ ] **3. Receiving domain.** Enable receiving for `inbound.caoscare.com` in Resend and add its MX record at GoDaddy. This gives `menu@inbound.caoscare.com` and `activities@inbound.caoscare.com` and leaves any `@caoscare.com` mail untouched.
- [ ] **4. Webhook.** One Resend webhook to `https://caoscare.com/api/email/inbound/resend`. Copy its `whsec_…` signing secret into `RESEND_WEBHOOK_SECRET` (without it the endpoint returns 503).
  - **Until Lane F is deployed, subscribe only `email.received`.** Production `d7ff96a` stores every event type as an inbound email, so a `delivered`/`bounced` event would be recorded as a bogus inbound message.
  - After Lane F is deployed, add `email.delivered`, `email.delivery_delayed`, `email.bounced`, `email.complained`, `email.failed`, `email.suppressed`.
- [ ] **5. Approved senders.** Name who may send the menu (for example the kitchen manager) and the activities schedule (for example the activities director). Exact address or a whole `@domain`. Entered in Admin. Any other sender is quarantined, not published.
- [ ] **6. Department addresses.** For nursing, maintenance, transportation, front desk (administration), kitchen, housekeeping and activities: a shared inbox per department (Admin → Departments → contact email), or real emails on each department's staff accounts. Admin/owner (Michael) is the last fallback.
- [ ] **7. Test recipients.** For acceptance, inboxes Michael controls, or the community's consent before mailing their real staff.
- [ ] **8. Decision: where the live test runs.** Resend only reaches a public URL. The EliteDesk is not public, so the live test runs on production (Linode) or through a tunnel to the EliteDesk. Mail sent by a non-public backend never receives its own delivery events.
- [ ] **9. Decision: release.** Setting the keys needs a backend restart. Delivery truth and fallback routing need Lane F integrated and a production release Michael approves.

Optional, not needed for email: Twilio SMS (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`).

## Code gaps (not Michael's)

| Gap | Owner | Status |
|---|---|---|
| Delivery truth, delivery-event routing and notice fallback | Lane F `0978bb1` | Built, tests only; integrate (order in `PILOT1_RECOVERY_CHECKPOINT.md` §4) |
| Notices linked to their request (`related_object_*` at every `notify_department` call site) | SC-8 | Open |
| Inbound activities email linked to its draft batch | CM-1 | Open |
| Three Twilio code paths with different env names; `twilio` package not in `requirements.txt` | Lane F | Open (SMS only) |
| Transportation itinerary inbox | — | Not built; only `menu` and `activities` lanes exist |
| Expected-information lifecycle: expected → missing → reminder due → sent → received → validating → needs review / valid → published → satisfied → new cycle; state-aware, friendly reminder emails that stop only once valid information is published | — | Not built in any branch. Needs a Shared Core / Lane F design and a ready-queue entry before work starts |

## Acceptance once configured

Lane F's list (`PILOT1_COMMUNICATIONS.md` §1, "Acceptance tests to run once configured") — none run yet:

- approved sender emails `menu@` with a `Date: YYYY-MM-DD` line → routed, menu upload, review/publish;
- approved sender emails `activities@` → routed, schedule items;
- unapproved sender → quarantined, nothing published;
- a real nursing, maintenance, transportation and front desk request → one notice per department, `sent` then `delivered`;
- department with no address, then an invalid address → falls through to the next tier, failure recorded;
- every step visible in Admin → Email & notifications.
