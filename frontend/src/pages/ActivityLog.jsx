import React, { useState } from "react";
import { Button } from "../components/ui/button";
import ReceiptsPanel from "./ReceiptsPanel";
import EventsPanel from "./EventsPanel";

// Admin activity log: two read-only browsers over data the system already
// records. Receipts = the operational-action log (task/request/device/alert
// lifecycle). Events = the append-only telemetry trace (Aria messages, tool
// calls, UI actions, device commands, auth). Neither view writes anything;
// both use the existing GET /receipts and GET /events endpoints.
export default function ActivityLog({ onNavigate }) {
  const [mode, setMode] = useState("receipts");
  return (
    <div className="space-y-4" data-testid="activity-log">
      <div>
        <h2 className="font-display text-2xl font-medium text-caos-forest">Activity log</h2>
        <p className="text-caos-mute text-sm mt-1">
          Every meaningful action, with who / when / where it stands. Read-only — this is the record, not a control surface.
        </p>
      </div>

      <div className="flex gap-2">
        <Button
          variant={mode === "receipts" ? "default" : "outline"}
          className={`rounded-full border-2 ${mode === "receipts" ? "bg-caos-forest" : ""}`}
          onClick={() => setMode("receipts")}
          data-testid="activity-mode-receipts"
        >
          Operational receipts
        </Button>
        <Button
          variant={mode === "events" ? "default" : "outline"}
          className={`rounded-full border-2 ${mode === "events" ? "bg-caos-forest" : ""}`}
          onClick={() => setMode("events")}
          data-testid="activity-mode-events"
        >
          Telemetry events
        </Button>
      </div>

      {mode === "receipts" ? <ReceiptsPanel onNavigate={onNavigate} /> : <EventsPanel />}
    </div>
  );
}
