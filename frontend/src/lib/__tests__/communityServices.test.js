import {
  SERVICES_DEPARTMENTS, menuStatusView, scheduleStatusView, groupDraftsByBatch,
  menuToolMessage, scheduleToolMessage,
} from "../communityServices";
import { executeOperationsTool } from "../realtimeOperationsTools";

describe("community services departments", () => {
  test("housekeeping, kitchen and activities use the services workspace", () => {
    expect(SERVICES_DEPARTMENTS).toEqual(["housekeeping", "kitchen", "activities"]);
  });
});

describe("menu / schedule status views", () => {
  test("only drafts can be published; replaced items never", () => {
    expect(menuStatusView("draft").canApprove).toBe(true);
    expect(menuStatusView("approved").canApprove).toBe(false);
    expect(menuStatusView("superseded").canApprove).toBe(false);
    expect(menuStatusView("superseded").label).toBe("Replaced");
    expect(scheduleStatusView("draft").canPublish).toBe(true);
    expect(scheduleStatusView("superseded").canPublish).toBe(false);
  });

  test("a schedule row stored before statuses existed counts as published", () => {
    expect(scheduleStatusView(undefined).label).toBe("Published");
  });
});

describe("groupDraftsByBatch", () => {
  test("groups by ingest batch, newest first, rows by date", () => {
    const groups = groupDraftsByBatch([
      { schedule_id: "a", ingest_id: "b1", date: "2026-10-06", created_at: "2026-10-01T10:00:00Z" },
      { schedule_id: "b", ingest_id: "b1", date: "2026-10-05", created_at: "2026-10-01T10:00:00Z" },
      { schedule_id: "c", ingest_id: "b2", date: "2026-10-07", created_at: "2026-10-02T10:00:00Z" },
    ]);
    expect(groups.map((g) => g.ingest_id)).toEqual(["b2", "b1"]);
    expect(groups[1].items.map((i) => i.schedule_id)).toEqual(["b", "a"]);
  });
});

describe("Aria menu/schedule answers", () => {
  test("an empty menu is honest and promises nothing", () => {
    const m = menuToolMessage([], { mealPeriod: "dinner", date: "2026-10-05" });
    expect(m).toMatch(/No approved dinner is on file for 2026-10-05/);
    expect(m).toMatch(/Nothing has been requested from the kitchen/);
    expect(m).not.toMatch(/get back to you/i);
  });

  test("menu lists the dishes with description and availability", () => {
    const m = menuToolMessage([{ meal_period: "lunch", item_name: "Tomato soup", description: "vegetarian", availability: "while supplies last" }]);
    expect(m).toBe("Approved menu for today: lunch: Tomato soup - vegetarian (while supplies last).");
  });

  test("schedule includes where, and an empty day is honest", () => {
    expect(scheduleToolMessage([{ time_label: "2:00 PM", title: "Bingo", description: "Main activity room" }], { date: "2026-10-05" }))
      .toBe("Schedule for 2026-10-05: 2:00 PM: Bingo (Main activity room).");
    expect(scheduleToolMessage([])).toMatch(/Nothing is listed on the schedule for today yet/);
  });
});

describe("executeOperationsTool - menu and schedule reads", () => {
  const realFetch = global.fetch;
  afterEach(() => { global.fetch = realFetch; });

  test("get_todays_schedule passes the requested date to the public read", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => [] });
    const r = await executeOperationsTool({ name: "get_todays_schedule", args: { date: "2026-10-06" }, ctx: {} });
    expect(global.fetch.mock.calls[0][0]).toMatch(/\/schedule\/public\/today\?date=2026-10-06$/);
    expect(r.message).toMatch(/for 2026-10-06/);
  });

  test("get_menu reads only the public (approved) endpoint", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => [{ meal_period: "dinner", item_name: "Baked chicken" }] });
    const r = await executeOperationsTool({ name: "get_menu", args: { meal_period: "dinner" }, ctx: {} });
    expect(global.fetch.mock.calls[0][0]).toMatch(/\/menu\/public\/today\?meal_period=dinner$/);
    expect(r).toEqual({ ok: true, message: "Approved menu for today: dinner: Baked chicken." });
  });
});
