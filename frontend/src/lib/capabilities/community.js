// Staff / community workflows for /for-communities. None has real staff
// acceptance yet, so each is a labelled description, not a demonstration.
// Status comes from status.js.
import { statusOf } from "./status";

export const COMMUNITY_WORKFLOWS = [
  { id: "nursing", name: "Nursing & care requests", department: "Nursing",
    summary: "A resident asks Aria for help and nursing gets one request in the resident's own words.",
    built: "Aria turns a spoken request into a nursing request with the resident's words and priority, and adds a repeat request to the open one instead of duplicating it. Staff can acknowledge, start and complete it on the requests board.",
    pending: "Nursing staff using it on shift has not been acceptance-tested." },
  { id: "maintenance", name: "Maintenance", department: "Maintenance",
    summary: "Repairs become work orders that are claimed, started and completed with notes.",
    built: "A maintenance workspace with work orders, assignment, progress, completion notes and time spent.",
    pending: "Not yet used and accepted by a maintenance team in real work." },
  { id: "transportation", name: "Transportation", department: "Transportation",
    summary: "Ride requests that stay pending until a driver and vehicle are assigned.",
    built: "Ride requests, a driver and vehicle calendar, and staff assignment.",
    pending: "No drivers or vehicles are set up, so every ride stays pending. Confirmation by staff has not been accepted." },
  { id: "dining", name: "Dining & menus", department: "Kitchen",
    summary: "The kitchen publishes the menu once and residents hear the same answer.",
    built: "Aria reads the approved menu and says when none has been published. Menus can be entered on screen or received by email.",
    pending: "A real kitchen email reaching residents after staff approval has not been tested." },
  { id: "activities", name: "Activities & programs", department: "Resident programs",
    summary: "Programs published once, available to residents by voice and on the room screen.",
    built: "Schedule intake; Aria and the room screen read today's published activities.",
    pending: "Community-specific publishing and staff use have not been set up or accepted." },
  { id: "housekeeping", name: "Housekeeping", department: "Housekeeping",
    summary: "Housekeeping requests reach the housekeeping queue.",
    built: "Requests route to a general housekeeping department queue.",
    pending: "There is no housekeeping-specific workflow yet, and the queue has not been accepted by staff." },
  { id: "front_desk", name: "Front desk workspace", department: "Front desk",
    summary: "One desk workspace for residents, requests and rides.",
    built: "A front desk workspace with the resident directory, request board and transportation calendar.",
    pending: "Not yet used and accepted by front desk staff." },
  { id: "front_desk_calls", name: "Calls to the front desk", department: "Front desk",
    summary: "\"Aria, call the front desk\" as a real two-way call.",
    pending: "Would place a real call and report whether it was answered, never claiming a call connected unless the phone system confirms it. Voice calling is not built yet." },
  { id: "administration", name: "Administration", department: "Leadership",
    summary: "One view of what needs attention, where every row opens the real record.",
    built: "An operations overview ranking open work, plus staff accounts, roles and departments.",
    pending: "Not yet accepted in real leadership use." },
  { id: "reporting", name: "Receipts, history & reporting", department: "Leadership",
    summary: "Actions leave records, and reports are built from those records.",
    built: "Receipts, an activity log, daily exceptions and weekly workload reports with CSV export.",
    pending: "Not yet accepted. Some receipts still record a status change by updating the previous entry rather than adding a new one." },
  { id: "escalation", name: "Alerts & escalation", department: "Nursing",
    summary: "Unanswered calls raised to the next level after set times.",
    built: "Configurable escalation levels that run when an administrator triggers them.",
    pending: "No automatic timer yet, and escalation has not been accepted." },
  { id: "therapy", name: "Therapy", department: "Therapy",
    summary: "Therapy visits and messages in the resident's own schedule.",
    pending: "Would let Aria answer questions about therapy visits and deliver messages from the therapist, with the sender's name." },
  { id: "beauty", name: "Beauty shop", department: "Salon",
    summary: "Salon requests that are only booked once the salon confirms.",
    pending: "Would record an appointment request and tell the resident it isn't booked until the salon confirms." },
].map((c) => ({ ...c, status: statusOf(c.id) }));

export const COMMUNITY_BY_ID = Object.fromEntries(COMMUNITY_WORKFLOWS.map((c) => [c.id, c]));

// Illustrative layout for the public staff dashboard demo. Not live data;
// each row shows its workflow's real development status.
export const DASHBOARD_ROWS = [
  { id: "r1", workflow: "nursing", time: "7:02 PM", room: "214", text: "Needs help getting to the bathroom", state: "Not acknowledged" },
  { id: "r3", workflow: "maintenance", time: "6:40 PM", room: "116", text: "Bathroom faucet dripping", state: "In progress" },
  { id: "r4", workflow: "transportation", time: "6:31 PM", room: "214", text: "Pharmacy, Tue 10:00", state: "Pending driver" },
  { id: "r5", workflow: "housekeeping", time: "6:15 PM", room: "305", text: "Change bed linens", state: "Pending" },
  { id: "r6", workflow: "front_desk", time: "5:50 PM", room: "221", text: "Callback about mail", state: "Pending" },
];
