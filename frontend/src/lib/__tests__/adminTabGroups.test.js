// Owner review: Kitchen and Transportation were missing from the Community
// (operations) group. Every department workspace lives there now, and no tab
// value appears in two groups (a duplicate would switch the group on click).
import { tabGroups } from "../adminTabGroups";

const groups = tabGroups([], [], [], [], { role: "owner" });

test("Community holds every department workspace including Kitchen and Transportation", () => {
  const community = groups.find((g) => g.id === "community").tabs.map((t) => t.value);
  for (const v of ["nursing", "maintenance", "housekeeping", "kitchen", "therapy", "activities", "transportation", "transport-calendar", "transport-log", "transport-resources"]) {
    expect(community).toContain(v);
  }
});

test("no tab value appears in two groups", () => {
  const all = groups.flatMap((g) => g.tabs.map((t) => t.value));
  expect(new Set(all).size).toBe(all.length);
});
