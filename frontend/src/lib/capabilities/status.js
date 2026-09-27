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

// Capability id -> status, with the evidence behind it (2026-09-27 audit).
export const CAPABILITY_STATUS = {
  // Resident room
  voice: "pilot", // live Room 214 conversations; started by screen tap; wake phrase not chosen
  lighting: "pilot", // Matter bulbs, HA read-back: live voice 09-05, touch 09-19, wake-word session 09-23; path unchanged since 7bad624
  rf_pendant: "pilot", // one Lifeline pendant (319.5 MHz) paired, decoded, battery/signal shown, Room 214
  help: "in_development", // request/event reaches staff screens; staff loop not accepted
  one_press: "in_development", // press -> event -> Aria live; staff close-out + recovery not accepted (2026-09-06 break test)
  low_vision: "in_development", // magnification built; not accepted with a resident
  tv: "in_development", // mock devices only; no real TV connected
  climate: "in_development", // test AC's Matter connection unreliable; no verified voice change
  blinds: "planned",
  location: "planned",
  family_call: "planned",
  handset: "planned",
  community_calls: "planned",
  answering_machine: "planned",
  wearables: "planned",
  // Community workflows: implementation exists, no real staff acceptance yet
  nursing: "in_development",
  maintenance: "in_development",
  transportation: "in_development",
  dining: "in_development",
  activities: "in_development",
  housekeeping: "in_development",
  front_desk: "in_development",
  administration: "in_development",
  reporting: "in_development",
  escalation: "in_development",
  front_desk_calls: "planned", // no voice telephony yet
  therapy: "planned",
  beauty: "planned",
};

export function statusOf(id) {
  const s = CAPABILITY_STATUS[id];
  if (!s) throw new Error(`Unknown capability: ${id}`);
  return s;
}

export const isDemonstrable = (status) => DEMONSTRABLE.has(status);
