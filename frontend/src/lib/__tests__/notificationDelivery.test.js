import { deliveryStatus, routeLabel, inboundStatus } from "../notificationDelivery";

describe("notification delivery truth", () => {
  test("only 'delivered' claims delivery", () => {
    for (const s of ["logged", "failed", "sent", "delayed", "bounced", "complained", "queued", "simulated"]) {
      expect(deliveryStatus(s).delivered).toBe(false);
    }
    expect(deliveryStatus("delivered").delivered).toBe(true);
  });

  test("logged is never presented as sent", () => {
    expect(deliveryStatus("logged").label).toMatch(/not sent/i);
    expect(deliveryStatus("sent").label).not.toMatch(/delivered/i);
  });

  test("simulated has a human label and is never presented as sent", () => {
    expect(deliveryStatus("simulated").label).toMatch(/simulated.*not sent/i);
  });

  test("unknown values degrade honestly", () => {
    expect(deliveryStatus("weird").label).toBe("weird");
    expect(deliveryStatus(undefined).label).toBe("Unknown");
    expect(routeLabel("nope")).toBeNull();
    expect(inboundStatus("quarantined").label).toMatch(/not approved/);
  });
});
