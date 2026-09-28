// Pure helpers for the community-services domains (dining/menu,
// activities/schedule, housekeeping). No JSX, no server calls - the staff
// pages, the resident Today panel and Aria's tool executor all read the
// same backend records (routes/menu.py, routes/schedule.py, StaffTask) and
// use these to present them consistently.

// Departments whose /workspace is the community-services view
// (CommunityServicesWorkspace.jsx). Maintenance and transportation keep
// their own views in DepartmentWorkspace.jsx.
export const SERVICES_DEPARTMENTS = ["housekeeping", "kitchen", "activities"];

export const MEAL_PERIODS = ["breakfast", "lunch", "dinner"];

// Menu item status -> what staff see. Only "approved" is ever read by
// residents or Aria (routes/menu.py::public_today). "superseded" items were
// replaced by a later approved upload and must not be re-approved from the
// list - they stay for history only.
const MENU_STATUS = {
  approved: { label: "Published", tone: "live", canApprove: false },
  draft: { label: "Draft", tone: "draft", canApprove: true },
  superseded: { label: "Replaced", tone: "old", canApprove: false },
};

export function menuStatusView(status) {
  return MENU_STATUS[status] || MENU_STATUS.draft;
}

// Schedule item status. Rows written before the draft/published split
// have no status and were always live, so a missing status is "published".
const SCHEDULE_STATUS = {
  published: { label: "Published", tone: "live", canPublish: false },
  draft: { label: "Draft", tone: "draft", canPublish: true },
  superseded: { label: "Replaced", tone: "old", canPublish: false },
};

export function scheduleStatusView(status) {
  return SCHEDULE_STATUS[status || "published"] || SCHEDULE_STATUS.published;
}

// Draft schedule rows grouped by the ingest batch (one pasted or emailed
// calendar) that produced them, newest batch first, rows by date.
export function groupDraftsByBatch(items) {
  const groups = new Map();
  for (const it of items || []) {
    const key = it.ingest_id || `single:${it.schedule_id}`;
    if (!groups.has(key)) groups.set(key, { ingest_id: it.ingest_id || null, source: it.source, created_at: it.created_at, items: [] });
    groups.get(key).items.push(it);
  }
  const out = [...groups.values()];
  for (const g of out) g.items.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
  return out.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
}

function dayWords(date) {
  return date ? date : "today";
}

// Aria's get_menu result text. Items come from /menu/public/today, which
// only ever returns approved items. An empty answer must stay honest: no
// promise to "check and get back", because nothing has been sent anywhere.
export function menuToolMessage(items, { mealPeriod = null, date = null } = {}) {
  const what = mealPeriod || "menu";
  if (!items || !items.length) {
    return `No approved ${what} is on file for ${dayWords(date)}. Tell the resident that honestly. ` +
      "Nothing has been requested from the kitchen - if they want, offer to ask the kitchen with " +
      "request_staff_help (category kitchen) and only say it was asked after that succeeds.";
  }
  const lines = items.map((i) =>
    `${i.meal_period}: ${i.item_name}${i.description ? ` - ${i.description}` : ""}${i.availability ? ` (${i.availability})` : ""}`);
  return `Approved menu for ${dayWords(date)}: ${lines.join("; ")}.`;
}

// Aria's get_todays_schedule result text (the endpoint already returns
// only published, resident-facing rows in time order).
export function scheduleToolMessage(items, { date = null } = {}) {
  if (!items || !items.length) {
    return `Nothing is listed on the schedule for ${dayWords(date)} yet. Say so honestly - do not invent an activity or time.`;
  }
  const lines = items.map((i) =>
    `${i.time_label ? `${i.time_label}: ` : ""}${i.title}${i.description ? ` (${i.description})` : ""}`);
  return `Schedule for ${dayWords(date)}: ${lines.join("; ")}.`;
}
