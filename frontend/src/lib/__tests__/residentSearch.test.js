import { matchResidents, scoreResident } from "../residentSearch";

const RESIDENTS = [
  { resident_id: "r1", name: "Helen Torres", preferred_name: "", room: "214" },
  { resident_id: "r2", name: "Helen Marsh", preferred_name: "Nell", room: "308" },
  { resident_id: "r3", name: "George Whitmore", preferred_name: "", room: "512" },
  { resident_id: "r4", name: "Torrence Bell", preferred_name: "", room: "21" },
  { resident_id: "r5", name: "Otis Freeman", preferred_name: "", room: "310" },
];

const ids = (list) => list.map((r) => r.resident_id);

describe("resident quick find", () => {
  test("room number: '214' finds Helen Torres first (exact room beats prefix)", () => {
    const r = matchResidents(RESIDENTS, "214");
    expect(r[0].resident_id).toBe("r1");
  });

  test("'21' prefix-matches 214 and 21 (both rooms), not names", () => {
    expect(ids(matchResidents(RESIDENTS, "21")).sort()).toEqual(["r1", "r4"].sort());
  });

  test("first name: 'Helen' finds both Helens", () => {
    expect(ids(matchResidents(RESIDENTS, "Helen")).sort()).toEqual(["r1", "r2"].sort());
  });

  test("last name: 'Torres' finds Helen Torres (and not Torrence, a first name substring is weaker)", () => {
    const r = matchResidents(RESIDENTS, "Torres");
    expect(r[0].resident_id).toBe("r1");
  });

  test("preferred name: 'Nell' finds Helen Marsh", () => {
    expect(ids(matchResidents(RESIDENTS, "Nell"))).toEqual(["r2"]);
  });

  test("'Helen Torres' phrase ranks Helen Torres above Helen Marsh", () => {
    const r = matchResidents(RESIDENTS, "Helen Torres");
    expect(r[0].resident_id).toBe("r1");
  });

  test("empty query returns nothing; unknown returns nothing", () => {
    expect(matchResidents(RESIDENTS, "")).toEqual([]);
    expect(matchResidents(RESIDENTS, "   ")).toEqual([]);
    expect(matchResidents(RESIDENTS, "zzzzz")).toEqual([]);
  });

  test("scales: with 300 residents a specific query still returns a short list", () => {
    const big = Array.from({ length: 300 }, (_, i) => ({
      resident_id: `b${i}`, name: `Person ${i} Lastname${i}`, preferred_name: "", room: `${400 + i}`,
    }));
    big.push({ resident_id: "needle", name: "Helen Torres", preferred_name: "", room: "214" });
    const r = matchResidents(big, "Torres", 8);
    expect(r.length).toBeLessThanOrEqual(8);
    expect(r[0].resident_id).toBe("needle");
    expect(matchResidents(big, "214")[0].resident_id).toBe("needle");
  });

  test("scoreResident is 0 for no match, positive for a match", () => {
    expect(scoreResident(RESIDENTS[0], "xyz")).toBe(0);
    expect(scoreResident(RESIDENTS[0], "helen")).toBeGreaterThan(0);
  });
});
