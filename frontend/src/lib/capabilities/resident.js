// Resident / family capabilities for the public site. Every card opens a
// panel (CapabilityPanel) with: visuals, the flow (what the resident does,
// what CAOSCare does, what staff see, what happens next), what is built
// today, and what is not yet accepted.
//
// Status comes from status.js; only proven capabilities are listed here.
// All names and rooms in screenshots are sample data.
import { statusOf } from "./status";
import { ILLUSTRATIONS, SCREENS } from "./visuals";

export const RESIDENT_CAPABILITIES = [
  {
    id: "voice",
    name: "Talk to Aria",
    summary: "Talk with Aria naturally from a chair or bed.",
    limitation: "Proven in the CAOSCare test room. A conversation starts with \"Hey Aria\" or a tap on the room screen; it can still take more than one try to be heard.",
    visuals: [ILLUSTRATIONS.talk, SCREENS.roomScreen, SCREENS.nursing],
    flow: {
      does: "Says \"Hey Aria\" or taps \"I just want to talk\" on the room screen, then speaks normally.",
      caos: "Knows which resident and room it is, and the name they prefer. Aria answers in her own voice through the room's speakerphone.",
      sees: "Authorized staff can read the conversation in the resident's record, with anything it created.",
      next: "When Aria doesn't know something, she says so rather than guessing.",
    },
    built: "Live spoken conversation with Aria in the test room, saved to the resident record.",
    pending: "Making sure \"Hey Aria\" is heard every time from anywhere in the room.",
  },
  {
    id: "help",
    name: "Ask for staff help",
    summary: "Ask Aria for help and the request goes to the right department in the resident's own words.",
    limitation: "Proven in the CAOSCare test room with test staff accounts. Staff handling these requests during a real shift has not been accepted yet.",
    visuals: [SCREENS.overview, SCREENS.recordsDrilldown, SCREENS.nursing],
    flow: {
      does: "Asks Aria for something, for example help getting to the bathroom.",
      caos: "Turns it into one request for the right department, with the resident's words and priority. A repeat request joins the open one.",
      sees: "Staff see the request on their board and can acknowledge, start and complete it.",
      next: "The resident sees the request on the room screen, and Aria reports its real status when asked.",
    },
    built: "Spoken requests become department requests with the resident's words, shown on the room screen and the staff board.",
    pending: "Staff handling these requests during a real shift has not been accepted.",
  },
  {
    id: "one_press",
    name: "One-press call for help",
    summary: "A single press brings Aria in and puts the call in front of staff.",
    limitation: "Proven in the CAOSCare test room. Staff acknowledging and closing calls during a real shift, and recovery if the connection drops, are still being tested.",
    visuals: [SCREENS.alerts, SCREENS.roomScreen, ILLUSTRATIONS.pendant],
    flow: {
      does: "Presses the help button on the room screen or a paired pendant.",
      caos: "Opens one assistance call for the room; repeat presses join it. Aria starts talking with the resident.",
      sees: "The call appears on the staff live board until someone acknowledges and closes it.",
      next: "Staff respond in person. Aria doesn't say anyone is on the way unless the record shows it.",
    },
    built: "The press opens one assistance call, starts Aria and shows on the staff live board.",
    pending: "Staff acknowledging and closing calls in normal work, and recovery if the connection drops.",
  },
  {
    id: "rf_pendant",
    name: "Paired pendant",
    summary: "A compatible help pendant paired to a resident and room.",
    limitation: "Proven with one pendant model (319.5 MHz) in the CAOSCare test room. It listens alongside the community's existing call system and never replaces it.",
    visuals: [ILLUSTRATIONS.pendant, SCREENS.pendants, SCREENS.alerts],
    flow: {
      does: "Presses their paired pendant.",
      caos: "The room's radio receiver decodes the press and matches it to this resident's pendant.",
      sees: "The pendant list shows the resident, signal, battery and last press; the call appears on the staff board.",
      next: "The press is recorded with its signal and battery condition, so staff can see the pendant is working.",
    },
    built: "Pairing, decoding and signal/battery tracking for one pendant model.",
    pending: "How staff respond to a pendant call is still in development; other pendant models need testing.",
  },
  {
    id: "lighting",
    name: "Lights",
    summary: "Lights on, off or to a brightness by voice or on the room screen.",
    limitation: "Proven with two smart bulbs in the CAOSCare test room. Other light models need testing before installation.",
    visuals: [SCREENS.roomControls, SCREENS.roomDemoDevices],
    flow: {
      does: "Says \"Aria, set the overhead light to fifty percent\", or uses the light control on the room screen.",
      caos: "Sends the command to that light, then reads back the light's actual state.",
      sees: "The room screen and the device record show the new state.",
      next: "Aria confirms only after the read-back matches; if it doesn't, she says it didn't work.",
    },
    built: "Voice and touch control of real bulbs, confirmed by read-back.",
    pending: "Testing other light models.",
  },
  {
    id: "tv",
    name: "Television",
    summary: "TV power, volume and mute by voice, and the TV quiets itself when Aria talks.",
    limitation: "Proven with one Sony TV in the CAOSCare test room, controlled by infrared. Infrared only sends commands, so CAOSCare cannot read back what the TV actually did.",
    visuals: [ILLUSTRATIONS.tv, SCREENS.roomControls],
    flow: {
      does: "Says \"Aria, turn on my TV\" or \"turn it down\", or uses the TV control on the room screen.",
      caos: "Sends the infrared command for that TV. When a conversation starts it mutes the TV, and restores the sound afterwards.",
      sees: "The device record shows the command that was sent.",
      next: "Aria says she sent the command; she doesn't claim the TV changed, because infrared can't confirm it.",
    },
    built: "Power, volume and mute for one TV model by infrared, plus automatic mute while Aria talks.",
    pending: "Other TV models, input switching, and confirming the TV's real state.",
  },
  {
    id: "climate",
    name: "Heating and cooling",
    summary: "Comfort requests turned into a temperature change, by voice or on the room screen.",
    limitation: "Proven on the CAOSCare demo room's thermostat. The test room's own air conditioner doesn't stay reliably connected, and each community's heating and cooling has to be connected and tested before it is switched on.",
    visuals: [SCREENS.roomDemoDevices, SCREENS.roomControls],
    flow: {
      does: "Says \"Aria, I'm cold\" or \"set it to 72\", or taps the thermostat control on the room screen.",
      caos: "Sends the new setting to the room's thermostat, then reads back the setting it actually has.",
      sees: "The device record shows the setting that was read back.",
      next: "Aria never says the room is warmer just because the setting changed.",
    },
    built: "Temperature commands by voice and touch, confirmed by read-back, shown here on the demo room's thermostat.",
    pending: "A real room's heating and cooling that stays connected; the test room's air conditioner drops off.",
  },
  {
    id: "low_vision",
    name: "Built for low vision",
    summary: "Voice first, with a room screen that can be enlarged.",
    limitation: "Proven in the CAOSCare test room: screen magnification by touch and voice, and a high-contrast mode. Not yet tested with residents who have low vision.",
    visuals: [SCREENS.roomContrast, SCREENS.roomEnlarged, SCREENS.roomScreen],
    flow: {
      does: "Uses the + and − buttons at the top of the room screen, asks Aria to make it bigger, or turns on high contrast.",
      caos: "Enlarges the whole room screen, from 50% to 200%, or switches it to high-contrast amber on black.",
      sees: "Nothing needs to go to staff.",
      next: "The size stays set on that room's screen.",
    },
    built: "Screen magnification by touch and by voice, and a high-contrast button.",
    pending: "Not yet tested with residents who have low vision.",
  },
  {
    id: "room_screen",
    name: "The room screen",
    summary: "One simple screen for help, talking to Aria, requests, today's plan and the room.",
    limitation: "Used in the CAOSCare test room. The TV there is real; the thermostat shown is the demo room's.",
    visuals: [SCREENS.roomScreen, SCREENS.roomControls, SCREENS.roomDemoDevices],
    flow: {
      does: "Sees their name, the time, a large help button and a talk button, with their requests, today's activities and menu, and room controls below.",
      caos: "Fills the screen from the same records Aria and staff use.",
      sees: "Staff update requests, schedules and menus in their own screens; the room screen follows.",
      next: "The TV stays the resident's TV; the screen is a companion, not a menu to learn.",
    },
    built: "The room screen with help, talk, requests, activities, menu and room controls.",
    pending: "A real room's heating and cooling on the screen; see that card.",
  },
  {
    id: "blinds",
    name: "Motorized blinds",
    summary: "Open, close or set the blinds by voice.",
    limitation: "Proven on the CAOSCare demo room's blinds. No blinds are installed in the test room yet, and each blind model has to be connected and tested before it is switched on.",
    visuals: [ILLUSTRATIONS.blinds, SCREENS.roomDemoDevices],
    flow: {
      does: "Says \"Aria, open the blinds\" or \"close them halfway\".",
      caos: "Sends the command to the room's blinds and reads back their position.",
      sees: "The device record shows the position the blinds report.",
      next: "Aria confirms only the position the blinds report; if the room has no blinds, she says so.",
    },
    built: "Open, close and set-to-a-percent by voice, confirmed by the reported position, proven on the demo room's blinds.",
    pending: "Installing and testing real motorized blinds in a resident's room.",
  },
].map((c) => ({ ...c, status: statusOf(c.id) }));

export const RESIDENT_BY_ID = Object.fromEntries(RESIDENT_CAPABILITIES.map((c) => [c.id, c]));
