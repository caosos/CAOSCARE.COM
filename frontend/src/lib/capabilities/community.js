// Staff / community workflows for /for-communities. Same panel shape as
// resident.js. Screens are the actual CAOSCare staff software, captured from
// an isolated demo database (sample data only). Workflows proven in the test
// environment are In pilot with their limits stated; none has real-shift
// staff acceptance yet, so none is Working (see status.js).
import { statusOf } from "./status";
import { ILLUSTRATIONS, SCREENS } from "./visuals";

export const COMMUNITY_WORKFLOWS = [
  {
    id: "staff_dashboard", name: "Staff dashboard", department: "All staff",
    summary: "The live board where staff see open calls, requests and device status.",
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.workspace, SCREENS.overview, SCREENS.recordsDrilldown],
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
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.nursing, SCREENS.recordsDrilldown],
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
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.maintenance, SCREENS.routing],
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
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.transportation],
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
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.kitchen],
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
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.schedule],
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
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.housekeeping],
    flow: {
      does: "Resident: \"Could I get some extra towels?\"",
      caos: "Routes the request to the housekeeping department.",
      sees: "The housekeeping workspace shows it; staff acknowledge, start and complete it.",
      next: "The resident's request status updates on the room screen.",
    },
    built: "Requests route to the housekeeping queue and workspace, including requests that repeat on a schedule.",
    pending: "Room rounds are not built yet, and housekeeping has not been accepted by staff in a real shift.",
  },
  {
    id: "front_desk", name: "Front desk", department: "Front desk",
    summary: "One desk workspace for residents, requests and rides.",
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.frontDesk],
    flow: {
      does: "Resident: \"Can the front desk call me about my mail?\"",
      caos: "Records a callback request for the desk.",
      sees: "The front desk workspace shows the request board next to today's rides and the resident directory.",
      next: "Desk staff follow up; the request status updates for the resident.",
    },
    built: "A front desk workspace with requests, the ride calendar and the resident directory.",
    pending: "Not yet used and accepted by front desk staff. Requests reach the desk as records, not phone calls: no phone system is connected.",
  },
  {
    id: "administration", name: "Administration & reporting", department: "Leadership",
    summary: "What needs attention, reports and a record of every action.",
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
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
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.alerts, SCREENS.escalation, SCREENS.routing],
    flow: {
      does: "Resident presses for help and nobody acknowledges it.",
      caos: "Raises the call's level after the set times and notifies the next contact.",
      sees: "Staff see open assistance events and their level; administrators set the times.",
      next: "Escalation stops when staff acknowledge the call.",
    },
    built: "The alerts list, escalation settings that administrators can change, and an automatic timer that raises unanswered calls, with every change receipted.",
    pending: "Which roles may acknowledge and close a call is still an owner decision.",
  },
  {
    id: "therapy", name: "Therapy", department: "Therapy",
    summary: "Therapy visits planned, tracked and shown in the resident's own schedule.",
    limitation: "Proven in the CAOSCare test environment with test staff accounts. Not yet used by a community's staff during a real shift.",
    visuals: [SCREENS.therapy],
    flow: {
      does: "Asks Aria \"When is my therapy today?\"",
      caos: "Reads the resident's planned therapy visits, including repeating visits and any linked ride.",
      sees: "Therapy staff plan, start and complete visits; overlapping bookings for the same therapist are flagged.",
      next: "Aria tells the resident the visit time, the therapist and where to go.",
    },
    built: "Therapy requests, planning, repeating visits, double-booking checks, linked rides and a resident \"Coming up\" list.",
    pending: "Not yet used by a community's therapy staff.",
  },
].map((c) => ({ ...c, status: statusOf(c.id) }));

export const COMMUNITY_BY_ID = Object.fromEntries(COMMUNITY_WORKFLOWS.map((c) => [c.id, c]));
