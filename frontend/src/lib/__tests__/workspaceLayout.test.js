import { defaultLayout, normalizeLayout, WIDGETS } from "../workspaceCatalog";
import { moveBox, stepBox } from "../useWorkspaceLayout";
import { periodParams } from "../useWorkspaceData";

test("default layout is the approved design's eight boxes in order", () => {
  expect(defaultLayout().map((b) => b.id)).toEqual(["resident_calls", "tasks_in_progress", "staff_on_duty",
    "residents", "kitchen", "housekeeping", "maintenance", "activities"]);
});

test("every box has a source; metric boxes name a backend metric", () => {
  for (const w of WIDGETS) {
    expect(["metric", "widget", "panel"]).toContain(w.source.kind);
    if (w.source.kind === "metric") expect(["done", "waiting", "in_progress", "open", "scheduled"]).toContain(w.source.metric);
  }
});

test("normalize drops unknown and duplicate boxes and clamps width", () => {
  const out = normalizeLayout([{ id: "kitchen", x: 3, w: 9 }, { id: "nope", x: 0 }, { id: "kitchen", x: 1 },
    { id: "residents", x: 2, w: 2, hidden: true }]);
  expect(out).toEqual([{ id: "residents", x: 0, y: 0, w: 2, h: 1, hidden: true },
                       { id: "kitchen", x: 1, y: 0, w: 4, h: 1 }]);
});

test("moving and stepping reorder boxes", () => {
  const boxes = defaultLayout();
  expect(moveBox(boxes, "kitchen", "resident_calls").map((b) => b.id).slice(0, 2)).toEqual(["kitchen", "resident_calls"]);
  const hidden = boxes.map((b) => (b.id === "staff_on_duty" ? { ...b, hidden: true } : b));
  // stepping skips hidden boxes
  expect(stepBox(hidden, "residents", -1).sort((a, b) => a.x - b.x).filter((b) => !b.hidden).map((b) => b.id).slice(0, 3))
    .toEqual(["resident_calls", "residents", "tasks_in_progress"]);
});

test("period parameters follow the selected world", () => {
  expect(periodParams({ world: "live", date: "2026-10-14" })).toEqual({ world: "live", date: "2026-10-14" });
  expect(periodParams({ world: "simulated", simDay: 9, date: "x" })).toEqual({ world: "simulated", sim_day: 9 });
});
