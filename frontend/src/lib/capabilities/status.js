// The one place CAOSCare's public capability status lives. Every public page
// (landing, /for-residents, /for-communities, /experience) reads status from
// here, so the same capability can never show two different stages.
//
// Rule (docs/CURRENT_PRIORITY.md): the website never claims or demonstrates a
// capability beyond its current acceptance evidence. Change a status only
// when that evidence changes, and record the evidence beside the entry.
//
// Owner policy 2026-10-16 (PR #181): a capability is In pilot once it is proven
// to work in the CAOSCare product/pilot architecture; it need not be installed
// in every room. The public site lists only Working and In pilot capabilities.
// Anything without that proof is not listed at all (never shown as Planned or
// In development, and never promoted to Pilot without its evidence).

export const STATUS_META = {
  working: {
    label: "Working",
    meaning: "Usable in real resident, staff or administrator work, and acceptance-tested.",
  },
  pilot: {
    label: "In pilot",
    meaning: "Proven to work in CAOSCare's pilot system, not yet in everyday use everywhere. Its limits are stated.",
  },
};

export const STATUS_ORDER = ["working", "pilot"];

// Capability id -> status, with the evidence behind it (2026-09-27 audit; re-audited 2026-10-16 for #162; 2026-10-12 owner direction:
// everything proven in the test room/environment is In pilot with its limits stated; 2026-10-16 owner policy above).
export const CAPABILITY_STATUS = {
  // Resident room
  voice: "pilot", // live Room 214 conversations; "Hey Aria" wake live since 10-08 (recall tuning in progress)
  lighting: "pilot", // Matter bulbs, HA read-back: live voice 09-05, touch 09-19, wake-word session 09-23; path unchanged since 7bad624
  rf_pendant: "pilot", // one Lifeline pendant (319.5 MHz) paired, decoded, battery/signal shown, Room 214
  room_screen: "pilot", // the room screen used live in Room 214 (tap to talk, light control 09-19)
  help: "pilot", // spoken requests -> department requests, staff/resident/Aria status; dev-accepted 10-11/12, owner direction 10-12
  one_press: "pilot", // press -> one event -> Aria; canonical ack/close receipts dev-accepted 10-12; owner direction 10-12
  low_vision: "pilot", // magnification (touch/voice) + high-contrast button on the room screen; owner direction 10-12
  tv: "pilot", // Room 214 Sony TV by infrared since 10-12 (ffeca1a, ir_blaster); call-start mute/restore physically accepted 10-12 (816f5f2); one-way IR, no read-back
  climate: "pilot", // owner policy 10-16: Aria adjust_room_temperature + room-screen thermostat with read-back, proven on the demo room's thermostat (demo_kiosk DEMO_BASELINE); Room 214's test AC connection unreliable
  blinds: "pilot", // owner policy 10-16: Aria set_blinds + room command path, proven on the demo room's blinds (demo_kiosk DEMO_BASELINE); no blinds installed in Room 214
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
  therapy: "pilot", // Therapy READY_FOR_OWNER_REVIEW 10-12 (32/32 dev checks); owner direction 10-12
};

export function statusOf(id) {
  const s = CAPABILITY_STATUS[id];
  if (!s) throw new Error(`Unknown capability: ${id}`);
  return s;
}
