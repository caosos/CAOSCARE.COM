// CAOSCare room capabilities shown in the public room experience.
//
// `status` comes from the single public status registry
// (lib/capabilities/status.js) so this page can never disagree with the
// rest of the site. `fixtures` = the room objects this capability attaches
// to (see communities.js).
import { STATUS_META, statusOf } from "../capabilities/status";

export const FEATURE_STATUS = STATUS_META;

export const ROOM_FEATURES = [
  {
    id: "voice",
    label: "Aria, the voice of the room",
    fixtures: ["room"],
    phrase: "Good morning, Aria.",
    what: "Speak from where you are — no screen, button or device to find.",
  },
  {
    id: "help",
    label: "Help, by voice or pendant",
    fixtures: ["bed", "chair"],
    phrase: "Aria, I need help.",
    what: "A spoken request or a press of a familiar pendant reaches staff.",
  },
  {
    id: "lighting",
    label: "Lighting",
    fixtures: ["lamp"],
    phrase: "Aria, turn on the lamp.",
    what: "Lamps on, off and dimmed by voice, with the result checked.",
  },
  {
    id: "tv",
    label: "Television",
    fixtures: ["tv"],
    phrase: "Aria, turn on the TV.",
    what: "Power and input by voice.",
  },
  {
    id: "climate",
    label: "Thermostat / heating and cooling",
    fixtures: ["thermostat"],
    phrase: "Aria, I'm cold.",
    what: "Comfort requests turned into a temperature change.",
  },
  {
    id: "blinds",
    label: "Motorized blinds",
    fixtures: ["window"],
    phrase: "Aria, open the blinds.",
    what: "Daylight and privacy without reaching for a cord.",
  },
  {
    id: "family_call",
    label: "Calling family",
    fixtures: ["room"],
    phrase: "Aria, call my daughter.",
    what: "Reach family by name, hands-free.",
  },
].map((f) => ({ ...f, status: statusOf(f.id) }));

export const FEATURES_BY_ID = Object.fromEntries(ROOM_FEATURES.map((f) => [f.id, f]));
