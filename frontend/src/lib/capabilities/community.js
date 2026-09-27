// Staff / community workflow demonstrations for /for-communities. Same five
// steps as the resident side. All residents, rooms, staff and times are
// sample data; nothing here reads the live backend.
import { statusOf } from "./status";

export const COMMUNITY_WORKFLOWS = [
  {
    id: "nursing", name: "Nursing & care requests", department: "Nursing",
    summary: "A resident asks for help and the nursing queue gets one request in the resident's own words.",
    steps: [
      { text: "Asks Aria for help.", quote: "Aria, I need help getting to the bathroom." },
      { text: "A nursing request, high priority because of fall risk. Not an emergency page." },
      { text: "One nursing request is created with the resident's words. If one is already open, it is added to that request instead of making a duplicate." },
      { text: "The nursing queue shows it.", sample: ["Room 214 · Helen (sample)", "\"Needs help getting to the bathroom\"", "High · Aria voice · 2 min ago · Not yet acknowledged"] },
      { text: "Aria tells the resident the request went to nursing. Once a nurse acknowledges it, Aria can say when. She doesn't say someone is on the way unless the record shows it.", quote: "I've sent that to the nursing staff." },
    ],
  },
  {
    id: "maintenance", name: "Maintenance", department: "Maintenance",
    summary: "Repairs become work orders that are claimed, started and completed with notes.",
    steps: [
      { text: "Reports a problem.", quote: "The faucet in my bathroom keeps dripping." },
      { text: "A maintenance request for Room 116: bathroom faucet." },
      { text: "A work order is created in the Maintenance queue with the resident's words." },
      { text: "The Maintenance workspace moves it from New to Claimed, In progress and Completed, with notes and time spent.", sample: ["Room 116 · Bathroom faucet dripping", "Claimed by D. Ruiz (sample) · In progress"] },
      { text: "Later the resident asks about it and Aria reads the real status.", quote: "Maintenance started on it this morning at 9:40." },
    ],
  },
  {
    id: "transportation", name: "Transportation", department: "Transportation",
    summary: "Ride requests stay pending until a driver and vehicle are actually assigned.",
    steps: [
      { text: "Asks for a ride.", quote: "I need a ride to the pharmacy Tuesday at ten." },
      { text: "A ride to the pharmacy, Tuesday at 10:00. If a time is missing, Aria asks instead of guessing one." },
      { text: "CAOSCare checks the configured drivers and vehicles. It books a run only if both are free; otherwise the request waits for the front desk." },
      { text: "The transportation calendar shows it.", sample: ["Tue 10:00 · Pharmacy · Room 214", "Pending · no driver assigned"] },
      { text: "Aria is clear that it isn't confirmed yet. When staff assign a driver, the status changes to confirmed.", quote: "Your ride request is in. It isn't confirmed yet; the front desk will confirm the time." },
    ],
  },
  {
    id: "dining", name: "Dining & menus", department: "Kitchen",
    summary: "The kitchen publishes the menu once and every room hears the same answer.",
    steps: [
      { text: "Asks about a meal.", quote: "What's for lunch?" },
      { text: "A question about today's lunch." },
      { text: "Aria reads today's approved menu. The kitchen sends the week's menu by email or enters it on the menu screen, and staff approve it before residents hear it." },
      { text: "The kitchen's menu screen.", sample: ["Today · Lunch · Approved", "Tomato soup · Turkey sandwich · Fruit cup"] },
      { text: "Aria reads the approved menu. If none is published, she says she doesn't have it yet.", quote: "Lunch is tomato soup and a turkey sandwich." },
    ],
  },
  {
    id: "activities", name: "Activities & programs", department: "Resident programs",
    summary: "Programs are published once and residents can ask about them by voice.",
    steps: [
      { text: "Asks what's on.", quote: "What's happening this afternoon?" },
      { text: "A question about today's program schedule." },
      { text: "Aria reads today's schedule as published by the activities staff. The same schedule appears on the room screen." },
      { text: "The schedule screen.", sample: ["2:00 PM · Bingo · Activity room", "3:30 PM · Book club · Library"] },
      { text: "Aria answers from the schedule. A change published once reaches every room.", quote: "Bingo is at two in the activity room." },
    ],
  },
  {
    id: "housekeeping", name: "Housekeeping", department: "Housekeeping",
    summary: "Housekeeping requests go to the housekeeping queue instead of getting lost in conversation.",
    steps: [
      { text: "Makes a request.", quote: "Could someone change my sheets today?" },
      { text: "A housekeeping request for Room 305." },
      { text: "The request goes to the Housekeeping department's queue." },
      { text: "The Housekeeping workspace shows it.", sample: ["Room 305 · Change bed linens", "Pending · Aria voice · 10 min ago"] },
      { text: "The status updates as staff start and complete it, and Aria reads that status if asked. Room-turn schedules and linen rounds are planned." },
    ],
  },
  {
    id: "therapy", name: "Therapy", department: "Therapy",
    summary: "Therapy visits and messages in the resident's own schedule.",
    steps: [
      { text: "Asks about a visit.", quote: "When is my therapy today?" },
      { text: "A question about the resident's therapy schedule." },
      { text: "Aria reads the resident's authorized therapy visits." },
      { text: "The therapy coordinator's view.", sample: ["Room 214 · Physical therapy · 11:00", "Reminder sent · Message from therapist (sample)"] },
      { text: "Aria answers and can deliver a message the therapist left, with the sender's name.", quote: "Physical therapy is at eleven, here in your room." },
    ],
  },
  {
    id: "beauty", name: "Beauty shop", department: "Salon",
    summary: "Salon requests that are only booked once the salon confirms.",
    steps: [
      { text: "Asks for an appointment.", quote: "Can I get my hair done Friday?" },
      { text: "A salon appointment request for Friday." },
      { text: "A request goes to the salon. Nothing is booked until the salon confirms a time." },
      { text: "The salon calendar.", sample: ["Fri · Room 214 · Wash and set", "Requested · awaiting salon"] },
      { text: "Aria says it's a request, not a booking, until the salon confirms.", quote: "I've asked the salon. It isn't booked until they confirm." },
    ],
  },
  {
    id: "front_desk", name: "Front desk", department: "Front desk",
    summary: "One desk workspace for requests, callbacks, rides and the resident directory.",
    steps: [
      { text: "Asks for the desk.", quote: "Please have the front desk call me back about my mail." },
      { text: "A callback request for the front desk." },
      { text: "The request goes to the desk's queue. If the resident already has one open, it is added to that one." },
      { text: "The Front Desk dashboard shows requests next to today's rides and the resident directory.", sample: ["Room 214 · Callback about mail", "Pending · 3 min ago"] },
      { text: "Aria tells the resident the desk has the request. Connecting a live phone call to the desk is planned; a recorded request and a connected call are different things.", quote: "The front desk has your callback request." },
    ],
  },
  {
    id: "administration", name: "Administration", department: "Leadership",
    summary: "One view of what needs attention, where every row opens the real record.",
    steps: [
      { text: "Residents in several rooms ask Aria for help, a ride and a repair during the morning." },
      { text: "Each request is sorted into its own department." },
      { text: "The operations overview ranks what needs attention: unacknowledged help calls first, then overdue work, rides with no slot and unassigned work." },
      { text: "The administrator's overview.", sample: ["Needs attention now · 4", "Room 214 · Help call · not acknowledged", "Room 116 · Faucet · unassigned 2 h"] },
      { text: "Clicking a row opens the underlying record. Staff accounts, roles and departments are managed from the same place." },
    ],
  },
  {
    id: "escalation", name: "Alerts & escalation", department: "Nursing",
    summary: "Unanswered calls are raised to the next level after set times.",
    steps: [
      { text: "Presses the pendant. No one acknowledges it." },
      { text: "An assistance call is open and has not been acknowledged." },
      { text: "Escalation raises the call's level after set times (for example 90 and 150 seconds) and can notify the next contact. Today this runs when an administrator triggers it; automatic timing is still being built." },
      { text: "The dashboard shows the level rising.", sample: ["Room 214 · Not acknowledged · 2:30", "Escalation level 2"] },
      { text: "Escalation stops when staff acknowledge the call, and every step stays in its history." },
    ],
  },
  {
    id: "reporting", name: "Receipts, history & reporting", department: "Leadership",
    summary: "Every action leaves a record, and reports are built from those same records.",
    steps: [
      { text: "Makes a request, for example a repair." },
      { text: "Each step of the request is recorded separately: created, assigned, started, completed." },
      { text: "Each step gets a receipt with who acted and when. The daily exceptions and weekly workload reports are built from the same records and can be exported to CSV." },
      { text: "The activity log and reports.", sample: ["9:12 · Request created · Aria voice", "9:40 · Started · D. Ruiz (sample)", "10:05 · Completed · 25 min"] },
      { text: "Leaders can trace any number back to the records behind it. Workload counts are volume, not a measure of staff performance." },
    ],
  },
].map((c) => ({ ...c, status: statusOf(c.id) }));

export const COMMUNITY_BY_ID = Object.fromEntries(COMMUNITY_WORKFLOWS.map((c) => [c.id, c]));

// Sample rows for the staff dashboard preview; each opens its workflow.
export const DASHBOARD_ROWS = [
  { id: "r1", workflow: "nursing", time: "7:02 PM", room: "214", text: "Needs help getting to the bathroom", state: "Not acknowledged" },
  { id: "r2", workflow: "escalation", time: "6:58 PM", room: "118", text: "Pendant call · level 2", state: "Escalated" },
  { id: "r3", workflow: "maintenance", time: "6:40 PM", room: "116", text: "Bathroom faucet dripping", state: "In progress" },
  { id: "r4", workflow: "transportation", time: "6:31 PM", room: "214", text: "Pharmacy, Tue 10:00", state: "Pending driver" },
  { id: "r5", workflow: "housekeeping", time: "6:15 PM", room: "305", text: "Change bed linens", state: "Pending" },
  { id: "r6", workflow: "front_desk", time: "5:50 PM", room: "221", text: "Callback about mail", state: "Pending" },
];
