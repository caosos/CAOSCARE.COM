// Staff / community workflows for /for-communities. Same panel shape as
// resident.js. Screens are the actual CAOSCare staff software, captured from
// an isolated demo database (sample data only). No staff workflow has real
// staff acceptance yet, so none is Working or In pilot (see status.js).
import { statusOf } from "./status";
import { PHOTOS, SCREENS } from "./visuals";

export const COMMUNITY_WORKFLOWS = [
  {
    id: "staff_dashboard", name: "Staff dashboard", department: "All staff",
    summary: "The live board where staff see open calls, requests and device status.",
    visuals: [SCREENS.staffDashboard, SCREENS.requestsBoard],
    flow: {
      does: "A resident asks Aria for help or presses the help button.",
      caos: "Creates the call or request and routes it to the right department.",
      sees: "Staff see it on the live board and the requests board, and can acknowledge, start and complete it.",
      next: "The resident's room screen and Aria reflect the real status.",
    },
    built: "The live board, the requests board and department workspaces.",
    pending: "Not yet accepted by staff in a real shift.",
  },
  {
    id: "nursing", name: "Nursing & care requests", department: "Nursing",
    summary: "A resident asks Aria for help and nursing gets one request in the resident's own words.",
    visuals: [SCREENS.requestDetail, SCREENS.requestsBoard, PHOTOS.caregiver],
    flow: {
      does: "Resident: \"Could you ask someone to help me to the bathroom?\"",
      caos: "Creates one high-priority nursing request with the resident's words. A repeat request joins the open one.",
      sees: "Nursing sees the request with the resident, room, time and priority, and acknowledges, starts and completes it.",
      next: "Aria can tell the resident the request was acknowledged, but not that someone is on the way unless the record shows it.",
    },
    built: "Spoken requests become nursing requests; staff can acknowledge, start and complete them.",
    pending: "Nursing staff using it on shift has not been acceptance-tested.",
  },
  {
    id: "maintenance", name: "Maintenance", department: "Maintenance",
    summary: "Repairs become work orders that are claimed, started and completed with notes.",
    visuals: [SCREENS.maintenance, PHOTOS.maintenance],
    flow: {
      does: "Resident: \"The faucet in my bathroom keeps dripping.\"",
      caos: "Creates a maintenance work order with the resident's words.",
      sees: "The maintenance workspace shows it as new, then claimed, in progress and completed, with notes and time spent.",
      next: "If the resident asks, Aria reads the work order's real status.",
    },
    built: "A maintenance workspace with work orders, assignment, progress, notes and completion.",
    pending: "Not yet used and accepted by a maintenance team in real work.",
  },
  {
    id: "transportation", name: "Transportation", department: "Transportation",
    summary: "Ride requests that stay pending until a driver and vehicle are assigned.",
    visuals: [SCREENS.transportCalendar, SCREENS.transportWorkspace],
    flow: {
      does: "Resident: \"I need a ride to the eye doctor tomorrow around two.\"",
      caos: "Records the ride request. If a time is missing, Aria asks instead of guessing one.",
      sees: "The transportation calendar shows confirmed rides and rides needing coordination; staff assign a time, driver and vehicle.",
      next: "Aria says a ride is confirmed only once staff have assigned it.",
    },
    built: "Ride requests, a driver and vehicle calendar, and staff assignment.",
    pending: "No real drivers or vehicles are set up at a community, and confirmation by staff has not been accepted.",
  },
  {
    id: "dining", name: "Kitchen, dining & menus", department: "Kitchen",
    summary: "The kitchen publishes the menu once and residents hear and see the same answer.",
    visuals: [SCREENS.menu, SCREENS.roomToday, SCREENS.kitchen],
    flow: {
      does: "Resident: \"What's for lunch?\"",
      caos: "Reads the approved menu; says so if none has been published.",
      sees: "The kitchen approves the menu on the menu screen and handles resident requests in its workspace.",
      next: "The same menu appears on every room screen.",
    },
    built: "Menu entry and approval, Aria reading the approved menu, and the menu on the room screen.",
    pending: "A real kitchen email reaching residents after staff approval has not been tested.",
  },
  {
    id: "activities", name: "Activities & resident programs", department: "Resident programs",
    summary: "Programs published once, available by voice and on the room screen.",
    visuals: [SCREENS.schedule, SCREENS.roomToday],
    flow: {
      does: "Resident: \"What's happening this afternoon?\"",
      caos: "Reads today's published schedule.",
      sees: "Activities staff publish the day's programs on the schedule screen.",
      next: "The same activities appear on every room screen.",
    },
    built: "Schedule intake, the schedule screen, Aria reading today's activities, and the room screen list.",
    pending: "Community-specific publishing and staff use have not been set up or accepted.",
  },
  {
    id: "housekeeping", name: "Housekeeping", department: "Housekeeping",
    summary: "Housekeeping requests reach the housekeeping queue.",
    visuals: [SCREENS.housekeeping],
    flow: {
      does: "Resident: \"Could I get some extra towels?\"",
      caos: "Routes the request to the housekeeping department.",
      sees: "The housekeeping workspace shows it; staff acknowledge, start and complete it.",
      next: "The resident's request status updates on the room screen.",
    },
    built: "Requests route to a general housekeeping queue and workspace.",
    pending: "No housekeeping-specific workflow yet (for example room rounds), and not accepted by staff.",
  },
  {
    id: "front_desk", name: "Front desk", department: "Front desk",
    summary: "One desk workspace for residents, requests and rides.",
    visuals: [SCREENS.frontDesk],
    flow: {
      does: "Resident: \"Can the front desk call me about my mail?\"",
      caos: "Records a callback request for the desk.",
      sees: "The front desk workspace shows the request board next to today's rides and the resident directory.",
      next: "Desk staff follow up; the request status updates for the resident.",
    },
    built: "A front desk workspace with requests, the ride calendar and the resident directory.",
    pending: "Not yet used and accepted by front desk staff. Live calls to the desk are planned (see the next card).",
  },
  {
    id: "front_desk_calls", name: "Calls to the front desk", department: "Front desk",
    summary: "\"Aria, call the front desk\" as a real two-way call.",
    visuals: [SCREENS.frontDesk],
    flow: {
      does: "Would say \"Aria, call the front desk.\"",
      caos: "Would place a real call to the desk.",
      sees: "The desk would receive a normal call, logged with the room.",
      next: "Aria would never claim a call connected unless the phone system confirms it.",
    },
    built: "The desk workspace only (shown). Voice calling is not built.",
    pending: "Planned: real calls to the desk with a clear call status.",
  },
  {
    id: "administration", name: "Administration & reporting", department: "Leadership",
    summary: "What needs attention, reports and a record of every action.",
    visuals: [SCREENS.overview, SCREENS.reports, SCREENS.activityLog],
    flow: {
      does: "Residents make requests and staff act on them through the day.",
      caos: "Records each action and ranks what needs attention.",
      sees: "Leaders see the operations overview, daily exceptions and weekly workload reports, and the activity log.",
      next: "Every row opens the underlying record; reports export to CSV.",
    },
    built: "Operations overview, reports with CSV export, activity log, and staff accounts, roles and departments.",
    pending: "Not yet accepted in real leadership use. Some status changes still update the previous record instead of adding a new one.",
  },
  {
    id: "escalation", name: "Alerts & escalation", department: "Nursing",
    summary: "Unanswered calls raised to the next level after set times.",
    visuals: [SCREENS.alertsBoard, SCREENS.escalation],
    flow: {
      does: "Resident presses for help and nobody acknowledges it.",
      caos: "Would raise the call's level after set times and notify the next contact.",
      sees: "Staff see open assistance events and their level; administrators set the times.",
      next: "Escalation stops when staff acknowledge the call.",
    },
    built: "The alerts list and escalation settings. Escalation runs when an administrator triggers it.",
    pending: "No automatic timer yet, and escalation has not been accepted.",
  },
  {
    id: "therapy", name: "Therapy", department: "Therapy",
    summary: "Therapy visits and messages in the resident's own schedule.",
    visuals: [PHOTOS.caregiver],
    flow: {
      does: "Would ask \"When is my therapy today?\"",
      caos: "Would read the resident's therapy visits.",
      sees: "The therapy coordinator would manage visits and leave messages with their name.",
      next: "Aria would deliver the message and the visit time.",
    },
    built: "Not built yet.",
    pending: "Planned.",
  },
  {
    id: "beauty", name: "Beauty shop", department: "Salon",
    summary: "Salon requests that are only booked once the salon confirms.",
    visuals: [PHOTOS.morning],
    flow: {
      does: "Would ask \"Can I get my hair done Friday?\"",
      caos: "Would record an appointment request.",
      sees: "The salon would confirm or offer another time.",
      next: "Aria would say it isn't booked until the salon confirms.",
    },
    built: "Not built yet.",
    pending: "Planned.",
  },
].map((c) => ({ ...c, status: statusOf(c.id) }));

export const COMMUNITY_BY_ID = Object.fromEntries(COMMUNITY_WORKFLOWS.map((c) => [c.id, c]));
