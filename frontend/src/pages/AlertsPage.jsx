import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { LogOut, ChevronLeft } from "lucide-react";
import AlertsBoard from "./AlertsBoard";
import { roleHomePath } from "../lib/roleHome";

// Standalone /alerts route chrome. AlertsBoard is also embedded as an Admin
// tab; this just gives it a header when a staff dashboard card links here.
export default function AlertsPage() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-caos-bone">
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link to="/" className="text-xl">
              <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
              <span className="font-display font-light text-caos-forest">Care</span>
            </Link>
            <Link to={roleHomePath(user)} className="text-sm text-caos-mute hover:text-caos-forest flex items-center gap-1" data-testid="alerts-back">
              <ChevronLeft className="w-4 h-4" /> Back
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-caos-mute hidden md:block">{user?.name}</span>
            <Button variant="outline" onClick={async () => { await logout(); nav("/login"); }} className="border-2 h-10 rounded-full" data-testid="alerts-logout">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <div className="max-w-6xl mx-auto px-6 py-8">
        <AlertsBoard />
      </div>
    </div>
  );
}
