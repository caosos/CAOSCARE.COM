import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { LogOut } from "lucide-react";
import { toast } from "sonner";
import TransportationCalendar from "./TransportationCalendar";
import RequestsBoard from "./RequestsBoard";

// Front Desk's own landing page (Section 7/8 of the Terminal 9 directive) -
// a role-focused operational view, not the full Admin interface. Reuses
// the same tasks/residents/transportation/requests components and
// endpoints Admin already reads - RequestsBoard specifically, so Front
// Desk and Admin can never see different answers about the same request.

function ResidentDirectory() {
  const [residents, setResidents] = useState([]);
  useEffect(() => {
    api.get("/residents").then(({ data }) => setResidents(data)).catch(() => toast.error("Could not load residents"));
  }, []);
  return (
    <Card className="border-caos-line p-6" data-testid="front-desk-residents">
      <h2 className="font-display text-xl font-medium text-caos-forest mb-4">Residents ({residents.length})</h2>
      <Table>
        <TableHeader>
          <TableRow><TableHead>Name</TableHead><TableHead>Room</TableHead></TableRow>
        </TableHeader>
        <TableBody>
          {residents.map((r) => (
            <TableRow key={r.resident_id}>
              <TableCell>{r.name}{r.preferred_name && <span className="text-caos-mute text-xs"> "{r.preferred_name}"</span>}</TableCell>
              <TableCell>{r.room}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

export default function FrontDeskDashboard() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-caos-bone">
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <Link to="/" className="text-xl">
            <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
            <span className="font-display font-light text-caos-forest">Care</span>
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-sm text-caos-mute hidden md:block">{user?.name} · Front desk</span>
            <Button variant="outline" onClick={logout} className="border-2 h-10 rounded-full" data-testid="front-desk-logout-btn">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        <h1 className="font-display text-4xl font-light text-caos-forest mb-2">Front desk</h1>
        <TransportationCalendar />
        <RequestsBoard />
        <ResidentDirectory />
      </div>
    </div>
  );
}
