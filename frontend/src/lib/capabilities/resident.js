// Resident-side capability demonstrations. Each walks through the same five
// steps (see steps.js). All names, rooms and times are sample data.
import { statusOf } from "./status";

export const RESIDENT_CAPABILITIES = [
  {
    id: "one_press",
    name: "One-press call",
    summary: "Press a familiar pendant or the room's help button. One press opens one call for help.",
    steps: [
      { text: "Presses the help pendant once, or taps the help button on the room screen." },
      { text: "The room node recognizes the press as coming from this resident's paired pendant. A pendant's routine check-in signal is ignored, and repeat presses join the same call instead of creating new ones." },
      { text: "One assistance event opens for the room and Aria starts talking with the resident." },
      { text: "The staff dashboard shows the open call.", sample: ["Room 214 · Helen (sample)", "Assistance requested · pendant · 1 press", "Open 0:42 · Awaiting staff"] },
      { text: "Aria tells the resident the call is on the staff screen and stays with them. She does not say anyone is on the way until staff acknowledge it. The call closes only when staff resolve it.", quote: "Your call is showing for the staff. I'm right here with you." },
    ],
  },
  {
    id: "voice",
    name: "Voice companion",
    summary: "Speak naturally from a chair or bed. Aria answers from the community's real information.",
    steps: [
      { text: "Asks a question out loud.", quote: "Aria, what's for dinner tonight?" },
      { text: "A question about tonight's published menu, not a request for staff." },
      { text: "Aria reads the dinner menu the kitchen published for today." },
      { text: "Nothing is sent to staff for an ordinary question. The conversation is kept in the resident's record for authorized staff." },
      { text: "Aria answers from the menu. If the kitchen hasn't published one, she says so instead of guessing.", quote: "Tonight is baked chicken, green beans and peach cobbler." },
    ],
  },
  {
    id: "location",
    name: "Building-wide location",
    summary: "Help calls that show where the resident is in the building.",
    steps: [
      { text: "Presses for help while in the dining room, wearing an approved device." },
      { text: "Compatible building sensors or the wearable report the resident's last known area." },
      { text: "The help call includes that area, not only the resident's room." },
      { text: "Staff see where to go.", sample: ["Room 214 · Helen (sample)", "Last seen: Dining room · 1 min ago"] },
      { text: "Staff go to the right place. Location is only shared where the resident has consented." },
    ],
  },
  {
    id: "low_vision",
    name: "Built for low vision",
    summary: "Voice first, with a room screen that can be enlarged by voice or touch.",
    steps: [
      { text: "Asks for bigger text.", quote: "Aria, make the screen bigger." },
      { text: "A request to change the room screen's size." },
      { text: "The screen enlarges, for example from 100% to 150%. It can go from 50% to 200%, and every control stays usable by voice." },
      { text: "Nothing needs to go to staff. The size stays set on that room's screen." },
      { text: "The screen is visibly larger and Aria confirms it.", quote: "I've made the screen bigger." },
    ],
  },
  {
    id: "rf_pendant",
    name: "Pendant (RF) integration",
    summary: "Pair a compatible help pendant to a resident and room, then test it.",
    steps: [
      { text: "Presses their pendant while staff set it up." },
      { text: "The room node's radio receiver records the pendant's signal (the tested pendant uses 319.5 MHz) and checks that it can't be confused with another resident's pendant." },
      { text: "The pendant is assigned to the resident and room. Each later press records signal strength and battery condition." },
      { text: "The devices screen shows the pendant.", sample: ["Helen's pendant (sample) · Room 214", "Signal good · Battery OK", "Last heard 2 min ago"] },
      { text: "A test press appears on the staff screen as that resident's call. Other pendant brands and frequencies need compatibility testing before installation." },
    ],
  },
  {
    id: "room_controls",
    name: "Room controls",
    summary: "Lights by voice today; TV, heating and cooling, and blinds are at earlier stages.",
    parts: [
      { id: "lighting", name: "Lights" },
      { id: "tv", name: "Television" },
      { id: "climate", name: "Heating and cooling" },
      { id: "blinds", name: "Motorized blinds" },
    ],
    steps: [
      { text: "Asks for a change.", quote: "Aria, turn the lamp down to half." },
      { text: "The lamp in this room, brightness 50%. If the room has two lamps, Aria asks which one." },
      { text: "The command goes to the lamp through the room's device connection, then the lamp's actual state is read back." },
      { text: "The device record shows the lamp at 50%, with the time and who asked.", sample: ["Room 214 · Desk lamp", "On · 50% · verified", "Asked by resident · 7:14 PM"] },
      { text: "Aria confirms only after the read-back matches. If she can't confirm it, she says so.", quote: "The lamp is at half now." },
    ],
  },
].map((c) => ({
  ...c,
  status: statusOf(c.id),
  parts: c.parts?.map((p) => ({ ...p, status: statusOf(p.id) })),
}));

export const RESIDENT_BY_ID = Object.fromEntries(RESIDENT_CAPABILITIES.map((c) => [c.id, c]));
