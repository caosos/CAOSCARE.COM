import { coverageMessage } from "../ContentCoverageNote";

test("no content today names the last published day and the next step", () => {
  const m = coverageMessage("menu", { covers_today: false, last_date: "2026-10-03", days_ago: 9, days_ahead: 0 });
  expect(m.tone).toBe("warn");
  expect(m.text).toBe("Residents and Aria have no menu for today. The last published day is 2026-10-03 (9 days ago). Paste or email the next menu, then publish it.");
});
test("nothing ever published", () => {
  expect(coverageMessage("schedule", { covers_today: false, last_date: null, days_ago: 0, days_ahead: 0 }).text)
    .toMatch(/^Residents and Aria have no activities for today\. Nothing has been published yet\./);
});
test("covered but running out soon, then fully covered", () => {
  expect(coverageMessage("menu", { covers_today: true, last_date: "2026-10-13", days_ahead: 2 }).text).toMatch(/^Published through 2026-10-13 only\./);
  expect(coverageMessage("menu", { covers_today: true, last_date: "2026-10-30", days_ahead: 19 })).toBeNull();
  expect(coverageMessage("menu", null)).toBeNull();
});
