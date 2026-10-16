import React, { useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Trash2, Plus, Volume2, DoorOpen, BookOpen } from "lucide-react";
import ResidentRecordDialog from "./ResidentRecordDialog";
import ResidentFormDialog from "./ResidentFormDialog";
import ResidentQuickFind from "./ResidentQuickFind";
import ResidentsCards from "./ResidentsCards";
import { useIsCompact } from "../lib/useIsCompact";
import { useResidentActions } from "../lib/useResidentActions";

/* -------------- Residents -------------- */
export default function ResidentsTab({ residents, kiosks, onChange, focusResidentId, onFocusHandled }) {
  const [formOpen, setFormOpen] = useState(false);
  const [editingResident, setEditingResident] = useState(null);
  const [recordFor, setRecordFor] = useState(null);

  // Deep-linked resident (/admin?resident=<id>, from a dashboard card or
  // Admin Aria) - open its record once the residents list is loaded.
  useEffect(() => {
    if (!focusResidentId || !residents?.length) return;
    const r = residents.find((x) => x.resident_id === focusResidentId);
    if (r) setRecordFor(r);
    onFocusHandled?.();
  }, [focusResidentId, residents]); // eslint-disable-line react-hooks/exhaustive-deps

  const open_new = () => { setEditingResident(null); setFormOpen(true); };
  const open_edit = (r) => { setEditingResident(r); setFormOpen(true); };

  const { kioskForRoom, enterRoom, setUpRoom, settingUpRoom, speakBriefing, briefingId, remove } =
    useResidentActions({ kiosks, onChange });

  const isCompact = useIsCompact();

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center gap-4 mb-4 flex-wrap">
        <h2 className="font-display text-xl font-medium text-caos-forest">Residents</h2>
        <ResidentQuickFind residents={residents} onPick={(r) => setRecordFor(r)} />
        <Button onClick={open_new} className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-resident-btn">
          <Plus className="w-4 h-4 mr-2" /> Add resident
        </Button>
      </div>
      {isCompact ? (
        <ResidentsCards
          residents={residents}
          kioskForRoom={kioskForRoom}
          enterRoom={enterRoom}
          setUpRoom={setUpRoom}
          settingUpRoom={settingUpRoom}
          speakBriefing={speakBriefing}
          briefingId={briefingId}
          openEdit={open_edit}
          remove={remove}
          setRecordFor={setRecordFor}
        />
      ) : (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead><TableHead>Room</TableHead><TableHead>Pendant</TableHead><TableHead>Participation</TableHead><TableHead>AI personalization</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {residents.map((r) => {
            const kiosk = kioskForRoom(r.room);
            return (
              <TableRow key={r.resident_id} data-testid={`res-row-${r.resident_id}`}>
                <TableCell>
                  <span className="font-medium">{r.name}</span>
                  {r.preferred_name && <span className="text-caos-mute text-xs block">"{r.preferred_name}"</span>}
                </TableCell>
                <TableCell>{r.room}</TableCell>
                <TableCell className="font-mono text-xs">{r.pendant_id}</TableCell>
                <TableCell className="text-xs uppercase tracking-wider font-bold text-caos-forest">{r.participation_level?.replace("_", " ") || "—"}</TableCell>
                <TableCell className="text-caos-mute text-sm max-w-xs truncate" title={r.preferences}>
                  {r.preferences ? `✓ ${r.preferences.slice(0, 60)}${r.preferences.length > 60 ? "…" : ""}` : <span className="text-caos-mute/50">—</span>}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    {kiosk ? (
                      <Button
                        variant="ghost" size="sm" onClick={() => enterRoom(r)}
                        data-testid={`enter-room-${r.resident_id}`}
                        title={`Open ${r.name}'s real kiosk experience in a new tab`}
                        className="text-caos-forest"
                      >
                        <DoorOpen className="w-4 h-4 mr-1" /> Enter room
                      </Button>
                    ) : (
                      <Button
                        variant="ghost" size="sm" onClick={() => setUpRoom(r.room)}
                        data-testid={`setup-room-${r.resident_id}`}
                        disabled={settingUpRoom === r.room}
                        title={`Room "${r.room}" has no kiosk yet — create it so this resident has a real room to enter`}
                        className="text-caos-terracotta"
                      >
                        <DoorOpen className="w-4 h-4 mr-1" /> {settingUpRoom === r.room ? "Setting up…" : "Set up room"}
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => speakBriefing(r)} data-testid={`brief-res-${r.resident_id}`} title="Speak a clinical briefing for this resident">
                      {briefingId === r.resident_id ? <span className="inline-flex items-center gap-1 text-caos-forest"><Volume2 className="w-4 h-4 animate-pulse" /> Speaking</span> : <span className="inline-flex items-center gap-1"><Volume2 className="w-4 h-4" /> Brief</span>}
                    </Button>
                    <Button
                      variant="ghost" size="sm" onClick={() => setRecordFor(r)}
                      data-testid={`record-res-${r.resident_id}`}
                      title="Resident hub — overview, conversations/transcripts, assistance events, requests, memory, movement, device"
                      className="text-caos-forest font-semibold"
                    >
                      <BookOpen className="w-4 h-4 mr-1" /> Resident hub
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => open_edit(r)} data-testid={`edit-res-${r.resident_id}`}>Edit</Button>
                    <Button variant="ghost" size="sm" onClick={() => remove(r.resident_id)} data-testid={`del-res-${r.resident_id}`}>
                      <Trash2 className="w-4 h-4 text-caos-terracotta" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      )}
      <ResidentFormDialog open={formOpen} onOpenChange={setFormOpen} resident={editingResident} kiosks={kiosks} onSaved={onChange} />
      <ResidentRecordDialog resident={recordFor} open={!!recordFor} onOpenChange={(o) => { if (!o) setRecordFor(null); }} />
    </Card>
  );
}
