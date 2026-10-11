import { detailsLine, detailsPayload } from "../appointmentDetails";

test("detailsLine words provider, kind and place the same way everywhere", () => {
  expect(detailsLine({ provider_name: "Tess Ortiz PT", discipline: "physical therapy", location: "Therapy room" }))
    .toBe("With: Tess Ortiz PT (physical therapy) · Where: Therapy room");
  expect(detailsLine({ discipline: "speech therapy" })).toBe("Kind: speech therapy");
  expect(detailsLine({ location: "Clinic downtown" })).toBe("Where: Clinic downtown");
  expect(detailsLine({})).toBe("");
  expect(detailsLine(null)).toBe("");
});

test("detailsPayload trims and sends empty strings so the server clears a field", () => {
  expect(detailsPayload({ provider: "  Tess  ", discipline: "", location: " Room 2 " }))
    .toEqual({ provider_name: "Tess", discipline: "", location: "Room 2" });
  expect(detailsPayload({})).toEqual({ provider_name: "", discipline: "", location: "" });
});
