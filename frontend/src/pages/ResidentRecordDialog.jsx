import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import {
  OverviewPanel,
  ConversationsPanel,
  AssistancePanel,
  RequestsPanel,
  DevicePanel,
} from "./ResidentHubPanels";
import MemoryPanel from "./MemoryDialog";
import MovementPanel from "./MovementDialog";

// Resident hub - one place to follow a resident's truth without remembering
// which internal module owns each record. Every section is a resident-filtered
// read over an EXISTING endpoint, and anything with its own workflow (an
// assistance event, a request) opens the SAME dialog the rest of Admin uses.
// Nothing new is stored; the underlying REQUESTS and ASSISTANCE EVENTS models
// stay separate - this only makes the distinction legible and links them.
// Memory + Movement were folded in from the two standalone dialogs the
// Residents row used to open.

const SECTIONS = [
  { key: "overview", label: "Overview" },
  { key: "conversations", label: "Conversations" },
  { key: "assistance", label: "Assistance events" },
  { key: "requests", label: "Resident requests" },
  { key: "memory", label: "Memory" },
  { key: "movement", label: "Movement" },
  { key: "device", label: "Device" },
];

export default function ResidentRecordDialog({ resident, open, onOpenChange, initialSection = "overview" }) {
  const [section, setSection] = useState(initialSection);

  useEffect(() => { if (open) setSection(initialSection); }, [open, initialSection, resident]);

  if (!resident) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto" data-testid="resident-record-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">
            {resident.name}
            {resident.room ? ` — Room ${resident.room}` : ""}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-wrap gap-1.5 mb-4" data-testid="resident-hub-nav">
          {SECTIONS.map((s) => (
            <button
              key={s.key}
              onClick={() => setSection(s.key)}
              data-testid={`resident-hub-tab-${s.key}`}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider transition-colors ${
                section === s.key
                  ? "bg-caos-forest text-white"
                  : "bg-white border border-caos-line text-caos-mute hover:border-caos-forest"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {section === "overview" && <OverviewPanel resident={resident} />}
        {section === "conversations" && <ConversationsPanel resident={resident} />}
        {section === "assistance" && <AssistancePanel resident={resident} />}
        {section === "requests" && <RequestsPanel resident={resident} />}
        {section === "memory" && <MemoryPanel resident={resident} />}
        {section === "movement" && <MovementPanel resident={resident} />}
        {section === "device" && <DevicePanel resident={resident} />}
      </DialogContent>
    </Dialog>
  );
}
