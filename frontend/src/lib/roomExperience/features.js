// CAOSCare room capabilities shown in the public room experience.
//
// `status` must reflect what CAOSCare has actually built — never what a
// community is promised. Update it only from evidence (docs/PROJECT_STATE.md):
//   pilot          working in the CAOSCare test room, not yet a general offering
//   in_development partially built / blocked on hardware
//   planned        designed or requested, not built
// `fixtures` = the room objects this capability attaches to (see communities.js).

export const FEATURE_STATUS = {
  pilot: { label: "In pilot", tone: "forest" },
  in_development: { label: "In development", tone: "amber" },
  planned: { label: "Planned", tone: "mute" },
};

export const ROOM_FEATURES = [
  {
    id: "voice",
    label: "Aria, the voice of the room",
    fixtures: ["room"],
    phrase: "Good morning, Aria.",
    what: "Speak from where you are — no screen, button or device to find.",
    status: "pilot",
  },
  {
    id: "help",
    label: "Help, by voice or pendant",
    fixtures: ["bed", "chair"],
    phrase: "Aria, I need help.",
    what: "A spoken request or a press of a familiar pendant reaches staff.",
    status: "pilot",
  },
  {
    id: "lighting",
    label: "Lighting",
    fixtures: ["lamp"],
    phrase: "Aria, turn on the lamp.",
    what: "Lamps on, off and dimmed by voice, with the result checked.",
    status: "pilot",
  },
  {
    id: "tv",
    label: "Television",
    fixtures: ["tv"],
    phrase: "Aria, turn on the TV.",
    what: "Power and input by voice.",
    status: "in_development",
  },
  {
    id: "climate",
    label: "Thermostat / heating and cooling",
    fixtures: ["thermostat"],
    phrase: "Aria, I'm cold.",
    what: "Comfort requests turned into a temperature change.",
    status: "in_development",
  },
  {
    id: "blinds",
    label: "Motorized blinds",
    fixtures: ["window"],
    phrase: "Aria, open the blinds.",
    what: "Daylight and privacy without reaching for a cord.",
    status: "planned",
  },
  {
    id: "family_call",
    label: "Calling family",
    fixtures: ["room"],
    phrase: "Aria, call my daughter.",
    what: "Reach family by name, hands-free.",
    status: "planned",
  },
];

export const FEATURES_BY_ID = Object.fromEntries(ROOM_FEATURES.map((f) => [f.id, f]));
