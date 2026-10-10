import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { LogOut, Plus, Bus } from "lucide-react";
import TransportationCalendar from "./TransportationCalendar";
import TransportLog from "./TransportLog";
import RequestsBoard from "./RequestsBoard";
import DepartmentQueue from "./DepartmentQueue";
import FrontDeskRequestForm from "../components/FrontDeskRequestForm";
import FrontDeskResidentDirectory from "../components/FrontDeskResidentDirectory";
import TransportRideForm from "../components/TransportRideForm";

// Front Desk's own landing page - a role-focused operational view, not the
// full Admin interface. Every section reads the same records Admin and the
// departments use: the front desk queue is the Administration department's
// StaffTask queue (Aria's "front desk" requests route there), rides are the
// shared transportation calendar, and "All requests" is the same
// RequestsBoard Admin sees.

const TABS = [
  ["requests", "Front desk requests"],
  ["transport", "Transportation"],
  ["ridelog", "Ride log"],
  ["residents", "Residents"],
  ["all", "All requests"],
];

export default function FrontDeskDashboard() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState("requests");
  const [reloadKey, setReloadKey] = useState(0);
  const [requestFor, setRequestFor] = useState(null); // resident_id or "" for a blank form
  const [rideFor, setRideFor] = useState(null);
  const reload = () => setReloadKey((k) => k + 1);

  return (
    <div className="min-h-screen bg-caos-bone">
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-y-2 px-4 sm:px-6 py-4">
          <Link to="/" className="text-xl">
            <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
            <span className="font-display font-light text-caos-forest">Care</span>
          </Link>
          <div className="flex items-center gap-3 overflow-x-auto max-w-full">
            <span className="text-sm text-caos-mute hidden md:block">{user?.name} · Front desk</span>
            <Button variant="outline" onClick={logout} className="border-2 h-10 rounded-full" data-testid="front-desk-logout-btn">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-4xl font-light text-caos-forest">Front desk</h1>
          <div className="flex gap-2">
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" onClick={() => setRequestFor("")} data-testid="fd-new-request-btn">
              <Plus className="w-4 h-4 mr-1" /> New request
            </Button>
            <Button variant="outline" className="border-2 rounded-full" onClick={() => setRideFor("")} data-testid="fd-new-ride-btn">
              <Bus className="w-4 h-4 mr-1" /> New ride
            </Button>
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto max-w-full" role="tablist">
          {TABS.map(([id, label]) => (
            <Button key={id} role="tab" aria-selected={tab === id} variant="outline" size="sm"
              className={`border-2 rounded-full shrink-0 ${tab === id ? "bg-caos-forest text-white" : ""}`}
              onClick={() => setTab(id)} data-testid={`fd-tab-${id}`}>{label}</Button>
          ))}
        </div>

        {tab === "requests" && (
          <DepartmentQueue key={reloadKey} department="administration" title="Front desk requests" adminMode />
        )}
        {tab === "transport" && <TransportationCalendar refreshKey={reloadKey} />}
        {tab === "ridelog" && <TransportLog />}
        {tab === "residents" && (
          <FrontDeskResidentDirectory reloadKey={reloadKey} onNewRequest={setRequestFor} onNewRide={setRideFor} />
        )}
        {tab === "all" && <RequestsBoard key={reloadKey} />}
      </div>

      <FrontDeskRequestForm open={requestFor !== null} onOpenChange={(o) => { if (!o) setRequestFor(null); }}
        residentId={requestFor || ""} onSaved={reload} />
      <TransportRideForm open={rideFor !== null} onOpenChange={(o) => { if (!o) setRideFor(null); }}
        residentId={rideFor || ""} onSaved={reload} />
    </div>
  );
}
