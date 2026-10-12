// The one place CAOSCare's public capability status lives. Every public page
// (landing, /for-residents, /for-communities, /experience) reads status from
// here, so the same capability can never show two different stages.
//
// Rule (docs/CURRENT_PRIORITY.md): the website never claims or demonstrates a
// capability beyond its current acceptance evidence. Change a status only
// when that evidence changes, and record the evidence beside the entry.

export const STATUS_META = {
  working: {
    label: "Working",
    tone: "forest",
    meaning: "Usable in real resident, staff or administrator work, and acceptance-tested.",
  },
  pilot: {
    label: "In pilot",
    tone: "moss",
    meaning: "Proven in the CAOSCare test room. Its limits are stated.",
  },
  in_development: {
    label: "In development",
    tone: "amber",
    meaning: "Partly built. The full loop with real users has not been accepted yet.",
  },
  planned: {
    label: "Planned",
    tone: "mute",
    meaning: "Not available yet.",
  },
};

export const STATUS_ORDER = ["working", "pilot", "in_development", "planned"];

// Statuses that may show a step-by-step demonstration.
export const DEMONSTRABLE = new Set(["working", "pilot"]);

// Capability id -> status, with the evidence behind it (2026-09-27 audit; 2026-10-12 owner direction:
// everything proven in the test room/environment is In pilot with its limits stated).
export const CAPABILITY_STATUS = {
  // Resident room
  voice: "pilot", // live Room 214 conversations; "Hey Aria" wake live since 10-08 (recall tuning in progress)
  lighting: "pilot", // Matter bulbs, HA read-back: live voice 09-05, touch 09-19, wake-word session 09-23; path unchanged since 7bad624
  rf_pendant: "pilot", // one Lifeline pendant (319.5 MHz) paired, decoded, battery/signal shown, Room 214
  room_screen: "pilot", // the room screen used live in Room 214 (tap to talk, light control 09-19)
  help: "pilot", // spoken requests -> department requests, staff/resident/Aria status; dev-accepted 10-11/12, owner direction 10-12
  one_press: "pilot", // press -> one event -> Aria; canonical ack/close receipts dev-accepted 10-12; owner direction 10-12
  low_vision: "pilot", // magnification (touch/voice) + high-contrast button on the room screen; owner direction 10-12
  tv: "in_development", // mock devices only; no real TV connected
  climate: "in_development", // test AC's Matter connection unreliable; no verified voice change
  blinds: "planned",
  location: "planned",
  family_call: "planned",
  phone: "planned", // handset, calls within the community, answering machine; no voice telephony yet
  wearables: "planned",
  // Community workflows: implementation exists, no real staff acceptance yet
  nursing: "pilot", // dev-accepted incl. unclaimed escalation, exception review; owner direction 10-12
  maintenance: "pilot", // dev-accepted department workspace; owner direction 10-12
  transportation: "pilot", // dev-accepted booking/runs/unresolved list; owner direction 10-12
  dining: "pilot", // menu draft/publish/correction versioning + dietary/allergen labels; owner direction 10-12
  activities: "pilot", // schedule draft/publish, resident Today panel; owner direction 10-12
  housekeeping: "pilot", // dev-accepted incl. recurring requests; owner direction 10-12
  front_desk: "pilot", // needs-attention inbox, failed deliveries, callback fields dev-accepted 10-12; owner direction 10-12
  administration: "pilot", // operations overview, reports, activity log; owner direction 10-12
  staff_dashboard: "pilot", // live board, current vs older split dev-accepted 10-12; owner direction 10-12
  escalation: "pilot", // automatic timer, receipted policy editor, liveness; Alerts dev-accepted 10-12; owner direction 10-12
  front_desk_calls: "planned", // no voice telephony yet
  therapy: "pilot", // Therapy READY_FOR_OWNER_REVIEW 10-12 (32/32 dev checks); owner direction 10-12
  beauty: "planned",
};

export function statusOf(id) {
  const s = CAPABILITY_STATUS[id];
  if (!s) throw new Error(`Unknown capability: ${id}`);
  return s;
}

export const isDemonstrable = (status) => DEMONSTRABLE.has(status);
