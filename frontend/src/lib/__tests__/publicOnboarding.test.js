// Carried over from PR #41: the room builder and the public catalogs must
// agree, and the built desk/schedule stay distinct from future calls.
import { RESIDENT_AREAS } from "../publicOnboarding";
import { FEATURES_BY_ID } from "../roomExperience/features";
import { RESIDENT_BY_ID } from "../capabilities/resident";
import { COMMUNITY_BY_ID } from "../capabilities/community";

test("resident room stages stay aligned with the room builder", () => {
  for (const id of ["voice", "lighting", "tv", "climate"]) {
    expect([id, RESIDENT_BY_ID[id].status]).toEqual([id, FEATURES_BY_ID[id].status]);
  }
  for (const id of ["blinds", "family_call"]) {
    expect([id, RESIDENT_AREAS.find((i) => i.id === id).status]).toEqual([id, FEATURES_BY_ID[id].status]);
  }
});

test("built schedule and desk are distinguished from future calls", () => {
  expect(COMMUNITY_BY_ID.activities.status).toBe("in_development");
  expect(COMMUNITY_BY_ID.front_desk.status).toBe("in_development");
  expect(COMMUNITY_BY_ID.front_desk_calls.status).toBe("planned");
});
