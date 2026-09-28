// The one list of images the public capability panels use.
//
// kind "screen" = a screenshot of the actual CAOSCare software, captured from
// an isolated demo database (every name, room and record is sample data).
// kind "photo"  = supplied lifestyle imagery. Illustrative only; it never
// stands in for a software screen.
//
// Screens were captured 2026-09-27 from integration/2026-09-27. Retake them
// when the underlying screen changes.

const screen = (file, width, height, alt) => ({ kind: "screen", src: `/media/screens/${file}`, width, height, alt });
const photo = (file, alt) => ({ kind: "photo", src: `/media/marketing/${file}`, width: 1672, height: 941, alt });
// kind "placeholder" = an honest stand-in where no relevant photo exists yet.
const placeholder = (file, alt) => ({ kind: "placeholder", src: `/media/placeholders/${file}`, width: 1600, height: 900, alt });

export const SCREENS = {
  roomScreen: screen("room-screen.jpg", 1100, 1506, "The resident's room screen: greeting, help button, talk button, requests, today's activities and menu, and room controls"),
  roomRequests: screen("room-screen-requests.jpg", 920, 175, "The resident's requests on the room screen, each with its department and status"),
  roomToday: screen("room-screen-today.jpg", 920, 241, "Today's activities and today's menu on the room screen"),
  roomControls: screen("room-screen-controls.jpg", 920, 263, "Room controls on the room screen: a lamp with brightness buttons, the TV and the thermostat"),
  conversation: screen("resident-conversation.jpg", 900, 604, "A resident's conversation with Aria in the staff resident record, with the requests and receipts it created"),
  requestsBoard: screen("requests-board.jpg", 1100, 696, "The resident requests board in the staff command centre"),
  requestDetail: screen("request-detail.jpg", 1100, 688, "A resident request opened for staff, with the resident's words, department, priority and status"),
  staffDashboard: screen("staff-dashboard.jpg", 1100, 696, "The staff live board with an open assistance call and device status"),
  alertsBoard: screen("alerts-board.jpg", 1100, 498, "The alerts and assistance events list"),
  escalation: screen("escalation.jpg", 1100, 447, "The escalation settings screen"),
  pendants: screen("pendants.jpg", 1100, 89, "The paired pendant list, with resident, frequency, signal, battery and last press"),
  maintenance: screen("maintenance-workspace.jpg", 1100, 498, "The maintenance workspace with a work order in progress"),
  housekeeping: screen("housekeeping-workspace.jpg", 1100, 361, "The housekeeping workspace with an open request"),
  kitchen: screen("kitchen-workspace.jpg", 1100, 361, "The kitchen workspace with a resident request"),
  menu: screen("menu-admin.jpg", 1100, 696, "The menu screen with approved items for today"),
  schedule: screen("schedule-admin.jpg", 1100, 481, "The daily schedule screen with today's activities"),
  transportCalendar: screen("transport-calendar.jpg", 1100, 602, "The transportation calendar with a confirmed ride and a ride needing coordination"),
  transportWorkspace: screen("transportation-workspace.jpg", 1100, 481, "The transportation workspace with open ride requests"),
  frontDesk: screen("front-desk.jpg", 1100, 696, "The front desk workspace with its calendar and request board"),
  overview: screen("operations-overview.jpg", 1100, 696, "The operations overview ranking what needs attention"),
  reports: screen("operations-reports.jpg", 1100, 696, "The daily exceptions report"),
  activityLog: screen("activity-log.jpg", 1100, 696, "The activity log of recorded actions"),
};

export const PHOTOS = {
  familyCall: photo("family-video-call-on-tv.png", "A resident in her armchair waving to her daughter and granddaughter on a video call on the TV"),
  caregiver: photo("caregiver-bedside-with-tablet.png", "A caregiver at a resident's bedside showing her a request list on a tablet"),
  morning: photo("resident-morning-in-bedroom.png", "A resident sitting up in bed in a sunny bedroom with window blinds"),
  maintenance: photo("maintenance-technician-at-sink.png", "A maintenance technician repairing a resident's bathroom sink while she looks on"),
};

export const PLACEHOLDERS = {
  therapy: placeholder("therapy.svg", "Placeholder: no therapy photo yet"),
  beauty: placeholder("beauty-shop.svg", "Placeholder: no beauty shop photo yet"),
};
