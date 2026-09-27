# CAOSCare public onboarding and sales package

**Product direction recorded 2026-09-27.** Read `AGENTS.md` and the Product
Baseline first. This package is the audience/website inventory; it does not
supersede architecture, implementation contracts, or current build evidence.
The current priority remains a reliable Resident Module.

## Builder onboarding: line count and modularity

Before editing code, read `AGENTS.md` → **Change discipline**, the canonical
rule. Keep implementation/UI files roughly within **300–400 lines** where
practical. Around **400 lines signals a split by coherent responsibility**;
it is not a hard cap or a reason for mechanical splitting. Do not materially
grow an already oversized implementation file; extract the changed
responsibility when practical. Information-dense docs/data may exceed that
range. At handoff report the line counts of every created or materially
modified production-code file. If the bounded change cannot be made without
substantially growing an oversized file and safe extraction is out of scope,
stop and report it. The full rule and its exceptions remain in `AGENTS.md`.

## Audience paths and the local showing

| Audience | Entry | What they should see |
|---|---|---|
| Resident | Local demonstration and `/for-residents` | Aria in the room, spoken requests, pendant, familiar phone design, messages, calling, room choices, clear availability |
| Family | Same local demonstration, shareable page/video and `/experience` | What the resident can control, how family calls/messages could work, which features this community actually has |
| Community buyer | `/for-communities` | Illustrated staff dashboard, departments, front desk, cross-department flow, rollout and support model |
| Actual staff member | `Staff sign in` → authenticated workspace | Their own authorized role/department workspace and actual records |

The public **Staff dashboard demo** is an illustrative walkthrough with
sample records. It never links to `/login`, exposes real resident data, or
pretends its sample buttons take real action. `Staff sign in` is the real
authenticated path. A local presentation uses the same resident/family
materials and a community-specific checklist of enabled services.

### Local introduction sequence

1. Meet the resident where they are: play the short resident film on a TV or
   phone and demonstrate ordinary speech in a test room.
2. Have the resident ask for a normal item (menu, light, maintenance status).
   Show the actual answer or the true pending state; use sample data only in
   an explicitly labelled demonstration.
3. Show what staff receive, who owns the next action, and the real receipt.
4. Show the familiar handset concept if appropriate: lift to Aria, ask to
   call the desk or a neighbor, hang up to end; demonstrate only when built.
5. Discuss the pendant separately for urgent help; show wearable and room
   options actually supported by that community.
6. Let family view the same materials and the specific consent/communication
   choices. Record package choice and installation readiness only in the
   future authorized ordering flow.

## Product inventory — website navigation

The site should expose the following through plain-language navigation and
expandable service/device groups. Every public capability carries its own
`Working`, `In pilot`, `In development`, or `Planned` label from build evidence.
All pages read that label from one registry,
`frontend/src/lib/capabilities/status.js`; change it there, from evidence only.

### Clickable capability panels (2026-09-27)

Every capability card on `/`, `/for-residents`, `/for-communities` and
`/experience` opens the same on-page panel (dialog; full-screen on phones):
title, status from `frontend/src/lib/capabilities/status.js`, visuals, what
the resident or staff member does, what CAOSCare does, what staff see, what
happens next, what is built today, and what is not yet accepted or still
planned. In-development and planned flows are worded as designs ("would"),
never as working features.

Visuals (`frontend/src/lib/capabilities/visuals.js`):
- `frontend/public/media/screens/`: screenshots of the actual CAOSCare
  software, captured from an isolated demo database (`caoscare_public_demo`
  on the EliteDesk, seeded by `backend/scripts/seed_demo_community.py`).
  Sample data only; retake when the screen changes.
- `frontend/public/media/marketing/`: the four supplied lifestyle images,
  labelled "Illustrative photo"; never a stand-in for a software screen.

## The familiar phone and answering machine

**Michael's intended interaction:** residents over 80 often already know
how to use a handset. Offer an old-style handset/cradle with few controls,
not an office VoIP phone screen. Picking up opens the resident's existing
Aria session; hanging up ends it. The handset is an audio/hook-switch
endpoint on the room node, sharing the same resident identity, tools,
requests and receipts as the room voice path. It is an option/fallback; the
active room baseline remains EliteDesk-class node + eMeet + TV.

- "Aria, call the front desk" reaches a single staffed destination with a
  queue or callback path. **Request recorded** and **voice call connected**
  are separate states.
- Resident-to-resident calls (neighbor/other room), nursing calls, family
  contacts and ordinary outside calls are design goals. Permissions,
  availability and routing must be explicit. Staff without a CAOSCare client
  can be reached through a controlled email/VoIP bridge where appropriate.
- The resident's room has its own answering-machine mailbox. Authorized
  front desk, nursing, Maintenance, therapy and family participants can
  leave attributed messages according to policy. Aria reports the **real**
  unread count and reads a real message on request; read/unread timestamps
  and sender remain tied to the canonical record. No invented messages.
- A roughly $79 Amazon front-desk phone and secondary desk laptop/dashboard
  were discussed as a practical pilot setup. The exact phone model,
  compatibility, price and procurement are **not verified or selected**.

## Approved devices and package configuration

The website should offer drop-down groups for **HELP pendants; approved
wearables; room audio/handset; lights/plugs; TV/IR; thermostat; blinds;
family communication**. Device choices come from a small tested catalog
(one or two approved manufacturers per class where practical), not an
unverified bring-your-own compatibility promise. Wearable data may include
heart rate, steps/activity, battery, approved location/proximity, and family
communication as supported and consented; actual device features vary.

The current `/experience` room builder uses **sample community and floor
plans** and lists voice, help, lights, TV, climate, blinds and family calls
with separate status. Extend it with community-approved devices, room
profile, selected services, installation/setup and transparent pricing when
those facts are verified. The proposed Basic / Connected / Full Smart Room
package labels and earlier $40/month discussion are **exploratory**, not
published prices or confirmed offerings. Do not invent a checkout.

## Ten-second story library

Create self-contained ~10-second segments that can be stitched into a
longer resident/family/community film. Show an action, the actual routing
or device response, then its visible result. Film as illustrative scenes
until the corresponding end-to-end path is proven. Each production entry
gets script, asset, poster, captions/transcript, capability status, owner,
source evidence, and website destination in the video catalog.

| Segment | Ten-second sequence | Public path |
|---|---|---|
| 001 · Room introduction | Resident speaks naturally → Aria replies → room responds | Resident/family |
| 002 · Staff handoff | Resident asks for a repair → request appears with original words → Maintenance acknowledges | Both |
| 003 · Ride | Resident asks for a ride → pending request → staff confirm time/driver | Community |
| 004 · Menu | Kitchen publishes dinner → resident asks → Aria reads the actual menu | Both |
| 005 · Care | Resident asks for assistance → care staff receive and acknowledge → Aria states verified status | Both |
| 006 · Programs | Community publishes an activity → resident asks → correct time/location | Both |
| 007 · Therapy and salon | Resident asks about visit/appointment → staff schedule or report pending | Both |
| 008 · Aria phone | Resident lifts familiar handset → Aria answers → resident requests a front-desk call | Resident/family |
| 009 · Neighbors and messages | Resident calls a neighbor or hears actual mailbox count → listens to message | Resident/family |
| 010 · Front desk | One call enters desk queue → person accepts or requests callback → accurate receipt | Community |
| 011 · Wearables | Resident presses HELP pendant → actual staff event appears; optional supported wearable information | Both |
| 012 · Leadership | Manager opens the same resident request and receipts from overview | Community |

Video #001 now uses a **nine-second greeting cut** from one continuous
resident/room scene: `frontend/public/media/caoscare-resident-greeting-01.mp4`
with poster and English VTT. The public list is
`frontend/src/lib/experienceVideos.js`. The earlier 30-second file remains
in the repo for editing reference but is no longer served in the public
library: it repeated a greeting, depicted several different residents as
"Margaret", showed planned calling and TV control as working, included a
Fox News-like logo, and ended mid-laugh. Recheck the new cut's audio and
caption timing locally before promoting it.

## Acceptance before publication or installation

- Website links: public community demo, resident/family page, sample room,
  and actual staff sign-in have distinct destinations and understandable
  labels on desktop and phone.
- Each service/device expansion shows what it does and its individual status.
  Sample records never expose resident data or call the live backend.
- Demonstration and sales claims match a dated, tested capability. Community
  availability, supported hardware, pricing and procurement require evidence.
- A real request or device action states `requested`, `acknowledged`,
  `assigned`, `completed`, `failed` or `unknown` according to actual records.
- Local onboarding verifies staff ownership, permissions, front desk routing,
  the room's equipment, and consent before enabling each function.
