import { COMMUNITY_AREAS, RESIDENT_AREAS, WEARABLE_AREAS } from "../publicOnboarding";
import { FEATURES_BY_ID } from "../roomExperience/features";

test("resident room stages stay aligned with the room builder", () => {
  const pairs = [
    ["Talk to the room", "voice"], ["Ask for staff help", "help"],
    ["Lighting", "lighting"], ["Television", "tv"],
    ["Thermostat & comfort", "climate"], ["Motorized blinds", "blinds"],
    ["Family connection", "family_call"],
  ];
  for (const [name, featureId] of pairs) {
    expect(RESIDENT_AREAS.find((item) => item.name === name)?.status)
      .toBe(FEATURES_BY_ID[featureId].status);
  }
  expect(WEARABLE_AREAS.find((item) => item.name === "Familiar HELP pendant")?.status)
    .toBe(FEATURES_BY_ID.help.status);
});

test("built schedule and desk are distinguished from future calls", () => {
  const stage = (id) => COMMUNITY_AREAS.find((item) => item.id === id)?.status;
  expect(stage("programs")).toBe("in_development");
  expect(stage("frontdesk")).toBe("in_development");
  expect(stage("calls")).toBe("planned");
});
