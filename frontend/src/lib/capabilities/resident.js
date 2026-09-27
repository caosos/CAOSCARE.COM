// Resident-side capabilities. Only capabilities with acceptance evidence
// (see status.js) carry `steps` and get a step-by-step demonstration; the
// rest carry `built` / `pending` text and are shown as labelled descriptions.
// Names, rooms and times in demonstrations are sample data.
import { statusOf } from "./status";

export const RESIDENT_CAPABILITIES = [
  {
    id: "voice",
    name: "Voice companion",
    summary: "Talk with Aria naturally from a chair or bed.",
    limitation: "Proven in the CAOSCare test room. A conversation is started by tapping the room screen; hands-free starting by a spoken phrase is still being chosen and tested.",
    steps: [
      { text: "Taps \"I just want to talk\" on the room screen and speaks normally." },
      { text: "Aria knows which resident and room she is in, and the name the resident prefers." },
      { text: "A live spoken conversation runs through the room's speakerphone." },
      { text: "Authorized staff can read the conversation in the resident's record." },
      { text: "Aria answers in her own voice. When she doesn't know something, she says so rather than guessing." },
    ],
  },
  {
    id: "lighting",
    name: "Lights",
    summary: "Turn lights on, off or to a brightness by voice or on the room screen.",
    limitation: "Proven with two smart bulbs in the CAOSCare test room. Other light models need to be tested before a community installation.",
    steps: [
      { text: "Asks for a change, or uses the light control on the room screen.", quote: "Aria, set the overhead light to fifty percent." },
      { text: "The overhead light in this room, brightness 50%." },
      { text: "The command goes to the light through the room's device connection, and the light's actual state is read back." },
      { text: "The room screen and the device record show the new state.", sample: ["Room 214 · Overhead light", "On · 50% · confirmed by read-back"] },
      { text: "Aria confirms only after the read-back matches. If it doesn't, she says it didn't work.", quote: "The overhead light is at fifty percent." },
    ],
  },
  {
    id: "rf_pendant",
    name: "Paired pendant",
    summary: "A compatible help pendant paired to a resident and room.",
    limitation: "Proven with one pendant model (319.5 MHz) in the CAOSCare test room. It listens alongside the community's existing call system and never replaces it. How staff respond to a press is still in development.",
    steps: [
      { text: "Presses their paired pendant." },
      { text: "The room node's radio receiver decodes the press and matches it to this resident's paired pendant." },
      { text: "An assistance event opens for the resident's room." },
      { text: "The devices screen shows the pendant's last signal.", sample: ["Helen's pendant (sample) · Room 214", "Signal good · Battery OK · Last heard 1 min ago"] },
      { text: "The press is recorded with its signal strength and battery condition, so staff can see the pendant is working." },
    ],
  },
  {
    id: "one_press",
    name: "One-press call for help",
    summary: "A single press brings Aria into the conversation and puts the call in front of staff.",
    built: "A pendant press or the room screen's help button opens one assistance event and starts Aria in the room.",
    pending: "Staff seeing, acknowledging and closing the call in normal work, and recovery if the connection drops, have not been accepted.",
  },
  {
    id: "low_vision",
    name: "Built for low vision",
    summary: "Voice first, with a room screen that can be enlarged.",
    built: "The room screen can be enlarged from 50% to 200% by voice or touch.",
    pending: "Not yet tested with residents who have low vision.",
  },
  {
    id: "tv",
    name: "Television",
    summary: "TV power, volume and input by voice.",
    built: "The voice commands and device records exist.",
    pending: "No real TV is connected yet; the control hardware for the test room still has to be chosen.",
  },
  {
    id: "climate",
    name: "Heating and cooling",
    summary: "Comfort requests turned into a temperature change.",
    built: "Temperature commands with read-back of the unit's actual setting.",
    pending: "The test room's air conditioner doesn't stay reliably connected, so no voice temperature change has been confirmed.",
  },
  {
    id: "location",
    name: "Building-wide location",
    summary: "Help calls that show where in the building the resident is.",
    pending: "Would attach a resident's last known area to a help call, using compatible building sensors or an approved wearable, only with consent.",
  },
].map((c) => ({ ...c, status: statusOf(c.id) }));

export const RESIDENT_BY_ID = Object.fromEntries(RESIDENT_CAPABILITIES.map((c) => [c.id, c]));
