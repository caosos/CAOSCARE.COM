import React from "react";
import { Button } from "../components/ui/button";
import { Trash2, Volume2, DoorOpen, BookOpen, ChevronDown } from "lucide-react";

// Compact (phone/tablet) presentation for the Residents list - same data,
// same handlers, same data-testids as ResidentsTab.jsx's <Table>, just
// stacked one-resident-per-card instead of columns, so nothing here is a
// second source of truth. Essential identity (name, room) and the primary
// action (Enter/Set up room, Edit) are always visible without scrolling;
// Pendant/Participation are shown as compact chips; the AI-personalization
// summary and the less-frequent actions (Brief, Resident hub, Delete) sit
// behind a native <details> disclosure - keyboard/screen-reader accessible
// with no extra JS state per card.
export default function ResidentsCards({
  residents, kioskForRoom, enterRoom, setUpRoom, settingUpRoom,
  speakBriefing, briefingId, openEdit, remove, setRecordFor,
}) {
  return (
    <div className="space-y-3" data-testid="residents-cards">
      {residents.map((r) => {
        const kiosk = kioskForRoom(r.room);
        return (
          <div key={r.resident_id} data-testid={`res-row-${r.resident_id}`} className="rounded-2xl border border-caos-line p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-medium text-caos-forest truncate">{r.name}</div>
                {r.preferred_name && <div className="text-caos-mute text-xs">"{r.preferred_name}"</div>}
              </div>
              <div className="shrink-0 rounded-full bg-caos-ambient px-3 py-1 text-xs font-bold uppercase tracking-wider text-caos-forest">
                Room {r.room}
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mt-3">
              <span className="rounded-full border border-caos-line px-2.5 py-1 text-xs font-mono text-caos-mute">{r.pendant_id || "no pendant"}</span>
              <span className="rounded-full border border-caos-line px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-caos-forest">
                {r.participation_level?.replace("_", " ") || "—"}
              </span>
            </div>

            <div className="flex flex-wrap gap-2 mt-3">
              {kiosk ? (
                <Button
                  variant="outline" size="sm" onClick={() => enterRoom(r)}
                  data-testid={`enter-room-${r.resident_id}`}
                  title={`Open ${r.name}'s real kiosk experience in a new tab`}
                  className="border-2 rounded-full text-caos-forest"
                >
                  <DoorOpen className="w-4 h-4 mr-1" /> Enter room
                </Button>
              ) : (
                <Button
                  variant="outline" size="sm" onClick={() => setUpRoom(r.room)}
                  data-testid={`setup-room-${r.resident_id}`}
                  disabled={settingUpRoom === r.room}
                  title={`Room "${r.room}" has no kiosk yet — create it so this resident has a real room to enter`}
                  className="border-2 rounded-full text-caos-terracotta"
                >
                  <DoorOpen className="w-4 h-4 mr-1" /> {settingUpRoom === r.room ? "Setting up…" : "Set up room"}
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => openEdit(r)} data-testid={`edit-res-${r.resident_id}`} className="border-2 rounded-full">
                Edit
              </Button>
            </div>

            <details className="mt-3 group">
              <summary className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-caos-mute cursor-pointer select-none list-none">
                <ChevronDown className="w-3.5 h-3.5 transition-transform group-open:rotate-180" /> More
              </summary>
              <div className="mt-3 space-y-3">
                {r.preferences && (
                  <p className="text-caos-mute text-sm">
                    <span className="font-semibold text-caos-forest">AI personalization: </span>
                    {r.preferences}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" size="sm" onClick={() => speakBriefing(r)} data-testid={`brief-res-${r.resident_id}`} title="Speak a clinical briefing for this resident">
                    {briefingId === r.resident_id
                      ? <span className="inline-flex items-center gap-1 text-caos-forest"><Volume2 className="w-4 h-4 animate-pulse" /> Speaking</span>
                      : <span className="inline-flex items-center gap-1"><Volume2 className="w-4 h-4" /> Brief</span>}
                  </Button>
                  <Button
                    variant="ghost" size="sm" onClick={() => setRecordFor(r)}
                    data-testid={`record-res-${r.resident_id}`}
                    title="Resident hub — overview, conversations/transcripts, assistance events, requests, memory, movement, device"
                    className="text-caos-forest font-semibold"
                  >
                    <BookOpen className="w-4 h-4 mr-1" /> Resident hub
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => remove(r.resident_id)} data-testid={`del-res-${r.resident_id}`}>
                    <Trash2 className="w-4 h-4 text-caos-terracotta mr-1" /> Delete
                  </Button>
                </div>
              </div>
            </details>
          </div>
        );
      })}
    </div>
  );
}
