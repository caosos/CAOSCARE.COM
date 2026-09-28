import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { driverHoursLabel } from "../lib/transportation";

const ANY = "__any";

// The resource part of booking a ride - pickup time, where to, and
// optionally a specific driver/vehicle. Shared by the Assign dialog and the
// staff New/Change ride form so both send the same fields to the same
// booking engine. "Any free" leaves the choice to the engine, which never
// picks a flex driver on its own.
export default function TransportResourceFields({ value, onChange, requireTime = false }) {
  const [drivers, setDrivers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  useEffect(() => {
    api.get("/transportation/drivers").then(({ data }) => setDrivers(data.filter((d) => d.enabled))).catch(() => setDrivers([]));
    api.get("/transportation/vehicles").then(({ data }) => setVehicles(data.filter((v) => v.enabled))).catch(() => setVehicles([]));
  }, []);
  const set = (patch) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <Label>Pickup time{requireTime ? "" : " (optional)"}</Label>
          <Input type="time" required={requireTime} value={value.start_time || ""}
            onChange={(e) => set({ start_time: e.target.value })} data-testid="ride-time-input" />
        </div>
        <div>
          <Label>Destination (optional)</Label>
          <Input value={value.destination || ""} placeholder="e.g. Conway Regional clinic"
            onChange={(e) => set({ destination: e.target.value })} data-testid="ride-destination-input" />
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <Label>Driver</Label>
          <Select value={value.driver_id || ANY} onValueChange={(v) => set({ driver_id: v === ANY ? "" : v })}>
            <SelectTrigger data-testid="ride-driver-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any free driver</SelectItem>
              {drivers.map((d) => (
                <SelectItem key={d.driver_id} value={d.driver_id}>
                  {d.name}{d.is_flex ? " (flex)" : ""} — {driverHoursLabel(d)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Vehicle</Label>
          <Select value={value.vehicle_id || ANY} onValueChange={(v) => set({ vehicle_id: v === ANY ? "" : v })}>
            <SelectTrigger data-testid="ride-vehicle-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any free vehicle</SelectItem>
              {vehicles.map((v) => (
                <SelectItem key={v.vehicle_id} value={v.vehicle_id}>
                  {v.name}{v.capacity != null ? ` (seats ${v.capacity})` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <p className="text-caos-mute text-xs">
        A ride only shares a vehicle with another resident when the destination matches exactly and the vehicle has a set capacity.
      </p>
    </div>
  );
}

// Strip empty strings so the backend sees "not chosen" rather than "".
export function resourcePayload(value) {
  const out = {};
  ["start_time", "destination", "driver_id", "vehicle_id"].forEach((k) => {
    if (value[k]) out[k] = value[k];
  });
  return out;
}
