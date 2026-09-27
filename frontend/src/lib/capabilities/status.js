// The one place CAOSCare's public capability status lives. Every public page
// (landing, /for-residents, /for-communities, /experience) reads status from
// here, so the same capability can never show two different stages.
//
// Change a status only from evidence (docs/PROJECT_STATE.md), never to match
// a sales promise. "working" still means: not yet running at a live community.

export const STATUS_META = {
  working: {
    label: "Working",
    tone: "forest",
    meaning: "Built and running in CAOSCare software. Not yet in use at a live community.",
  },
  pilot: {
    label: "In pilot",
    tone: "moss",
    meaning: "Running in the CAOSCare test room with real devices. Not yet in use at a live community.",
  },
  in_development: {
    label: "In development",
    tone: "amber",
    meaning: "Partly built. Parts of this demonstration do not work yet.",
  },
  planned: {
    label: "Planned",
    tone: "mute",
    meaning: "Designed, not built. This demonstration shows the intended design only.",
  },
};

export const STATUS_ORDER = ["working", "pilot", "in_development", "planned"];

// Capability id -> status. Evidence notes are kept beside each entry.
export const CAPABILITY_STATUS = {
  // Resident room
  voice: "pilot", // Room 214 Realtime sessions with the eMeet
  help: "pilot", // spoken help + paired pendant, Room 214
  one_press: "pilot", // paired Lifeline pendant opens one assistance event
  rf_pendant: "pilot", // Nooelec SDR + rtl_433, pairing guard, 319.5 MHz
  lighting: "pilot", // real Matter bulbs, verified by read-back
  room_controls: "pilot", // lights pilot; TV/climate in development; blinds planned
  tv: "in_development", // mock devices + input capability only
  climate: "in_development", // Midea AC Matter session unstable
  blinds: "planned",
  low_vision: "working", // 50-200% magnification by voice or touch
  location: "planned", // no building sensors integrated
  family_call: "planned",
  handset: "planned",
  community_calls: "planned",
  answering_machine: "planned",
  wearables: "planned",
  // Community workflows
  nursing: "pilot", // resident request routing, Room 214
  maintenance: "working", // work-order workspace
  transportation: "in_development", // engine + calendar; no automatic confirmation
  dining: "pilot", // Aria answers from the published menu
  activities: "working", // schedule ingest + get_todays_schedule + Today panel
  housekeeping: "working", // department queue; room-turn tracking planned
  therapy: "planned",
  beauty: "planned",
  front_desk: "working", // desk dashboard + role; voice calls planned
  administration: "working", // operations overview, users & access
  escalation: "in_development", // no automatic timer; two implementations
  reporting: "working", // receipts, activity log, reports, CSV
};

export function statusOf(id) {
  const s = CAPABILITY_STATUS[id];
  if (!s) throw new Error(`Unknown capability: ${id}`);
  return s;
}
