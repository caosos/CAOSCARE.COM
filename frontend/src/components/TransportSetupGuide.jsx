import React from "react";
import { Card } from "./ui/card";
import { transportSetupStatus } from "../lib/transportation";

// Plain-language purpose and setup for Transport resources, plus whether rides
// can be booked right now (read from the same driver/vehicle lists below).
export default function TransportSetupGuide({ drivers, vehicles }) {
  const st = transportSetupStatus(drivers, vehicles);
  return (
    <Card className="border-caos-line p-5" data-testid="transport-setup-guide">
      <h2 className="font-display text-lg font-medium text-caos-forest">What this screen is for</h2>
      <p className="text-sm text-caos-ink mt-1">
        The drivers and vehicles CAOSCare is allowed to book. When the front desk or transportation staff assign a ride,
        CAOSCare only picks an enabled driver who is working at the pickup time and an enabled vehicle with enough seats.
      </p>
      <ol className="list-decimal pl-5 text-sm text-caos-ink mt-3 space-y-1">
        <li><b>Add each driver</b> and set their working days and hours (click the hours in their row).</li>
        <li><b>Link the driver's login</b> if they sign in, so they see "My rides".</li>
        <li><b>Add each vehicle</b> with its real seat count. Without a seat count it can still take one resident, but CAOSCare will not share it.</li>
        <li><b>Check the scheduling buffer</b>: the minimum gap between two runs for the same driver or vehicle.</li>
      </ol>
      <div className={`mt-4 rounded-lg px-3 py-2 text-sm ${st.ready ? "bg-caos-moss/15 text-caos-forest" : "bg-amber-50 text-amber-900"}`} data-testid="transport-setup-status">
        {st.ready
          ? `Ready to book rides: ${st.bookableDrivers} driver(s) and ${st.vehicles} vehicle(s) available.`
          : `Rides cannot be booked automatically yet. Still needed: ${st.missing.join("; ")}. Requests still arrive and wait in "Needs coordination".`}
        {st.sharingOff && <div className="mt-1" data-testid="transport-sharing-off">No vehicle has a seat count yet, so residents going the same way will not be put on one ride.</div>}
      </div>
    </Card>
  );
}
