import { roomCallCostLabel } from "../RoomCallCost";

test("labels complete, incomplete, failed and missing usage honestly", () => {
  expect(roomCallCostLabel({ environment: "live", call_status: "ended", estimate_status: "complete", estimated_usd: 0.0015 }))
    .toBe("Last call estimated $0.0015");
  expect(roomCallCostLabel({ environment: "development_test", call_status: "ended", estimate_status: "incomplete", known_estimated_usd: 0.00002 }))
    .toBe("Test call at least <$0.0001 · incomplete usage");
  expect(roomCallCostLabel({ environment: "live", call_status: "failed", estimate_status: "unknown", known_estimated_usd: null }))
    .toBe("Last call cost unknown · usage unavailable · failed");
  expect(roomCallCostLabel({ call_status: "no_call" })).toBe("No call receipt");
  expect(roomCallCostLabel(null)).toBe("Call cost unavailable");
});
