import { seriesLabel, templatePayload } from "../recurrence";

test("series label says when it repeats", () => {
  expect(seriesLabel({ recur: "weekly", weekday: 1, time_label: "9:00 AM" })).toBe("Every Tuesday at 9:00 AM");
  expect(seriesLabel({ recur: "daily" })).toBe("Every day");
});

test("payload sends the series fields the server keeps", () => {
  const p = templatePayload({ title: " Weekly clean ", description: "", category: "other", shift: "any", recur: "weekly",
    weekday: "1", time_label: "9:00 AM", department: "housekeeping", resident_id: "r1" });
  expect(p).toEqual({ title: "Weekly clean", description: "", category: "housekeeping", shift: "any", recur: "weekly",
    weekday: 1, time_label: "9:00 AM", department: "housekeeping", resident_id: "r1" });
  expect(templatePayload({ title: "x", recur: "daily", shift: "any", category: "other" }).weekday).toBeUndefined();
});

test("payload carries appointment details when given", () => {
  const p = templatePayload({ title: "PT", recur: "weekly", weekday: "2", shift: "any", category: "other", department: "therapy",
    provider_name: " Pat Lee, PT ", discipline: "Physical therapy", location: "", time_label: "10:00 AM" });
  expect(p.provider_name).toBe("Pat Lee, PT");
  expect(p.discipline).toBe("Physical therapy");
  expect(p.location).toBeUndefined();
});
