import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Trash2, Plus, Volume2, DoorOpen, BookOpen } from "lucide-react";
import { toast } from "sonner";
import MovementDialog from "./MovementDialog";
import MemoryDialog from "./MemoryDialog";
import ResidentRecordDialog from "./ResidentRecordDialog";
import ResidentFormDialog from "./ResidentFormDialog";

/* -------------- Residents -------------- */
export default function ResidentsTab({ residents, kiosks, onChange }) {
  const [formOpen, setFormOpen] = useState(false);
  const [editingResident, setEditingResident] = useState(null);
  const [movementFor, setMovementFor] = useState(null);
  const [memoryFor, setMemoryFor] = useState(null);
  const [recordFor, setRecordFor] = useState(null);

  const open_new = () => { setEditingResident(null); setFormOpen(true); };
  const open_edit = (r) => { setEditingResident(r); setFormOpen(true); };

  const remove = async (id) => {
    if (!window.confirm("Delete this resident?")) return;
    await api.delete(`/residents/${id}`);
    toast.success("Deleted");
    onChange();
  };

  // Voice briefing — fetches the narrative then streams the pre-composed line
  // through OpenAI TTS so the nurse can literally hear the resident's
  // clinical bands + open alerts + cheat-sheet memories without reading.
  const [briefingId, setBriefingId] = useState(null); // resident_id currently speaking
  const audioRef = React.useRef(null);
  const speakBriefing = async (r) => {
    try {
      // Stop any in-flight playback
      if (audioRef.current) { try { audioRef.current.pause(); } catch {} audioRef.current = null; }
      setBriefingId(r.resident_id);
      const { data: brief } = await api.get(`/residents/${r.resident_id}/briefing`);
      const { data: tts } = await api.post("/ai/tts", { text: brief.narrative, voice: "sage" });
      const audio = new Audio(`data:audio/mp3;base64,${tts.audio_base64}`);
      audioRef.current = audio;
      audio.onended = () => { if (audioRef.current === audio) { audioRef.current = null; setBriefingId(null); } };
      audio.onerror = () => { setBriefingId(null); toast.error("Briefing playback failed"); };
      await audio.play();
      toast.success(`Briefing: ${r.name}`);
    } catch (err) {
      setBriefingId(null);
      toast.error(err?.response?.data?.detail || "Briefing failed");
    }
  };

  // Enter Room — the resident↔kiosk link is a room-string match (Kiosk.room
  // === Resident.room), the same lookup /residents/public/by-kiosk/{id} does
  // server-side. Resolved client-side from the kiosks list Admin.jsx already
  // fetches, so a resident with no matching kiosk shows that plainly instead
  // of silently opening an unrelated room's kiosk.
  const kioskForRoom = (room) => (kiosks || []).find((k) => k.room === room);
  const enterRoom = (r) => {
    const kiosk = kioskForRoom(r.room);
    if (!kiosk) {
      toast.error(`No kiosk mapped to room "${r.room}" — nothing to open.`);
      return;
    }
    window.open(`/kiosk/${kiosk.kiosk_id}`, "_blank", "noopener");
  };

  // "Set up room" — creates the real logical kiosk record for this room via
  // the same POST /kiosks Admin → Kiosks' own "Add kiosk" uses (no separate
  // provisioning system). Once it exists, Enter Room resolves it immediately
  // via the same room-string match above - real path, not a simulator.
  // Physical tablet install (Admin → Kiosks → Install) is a later, separate
  // step; this only creates the logical room/kiosk association a browser
  // acceptance test needs.
  const [settingUpRoom, setSettingUpRoom] = useState(null); // room currently being set up
  const setUpRoom = async (room) => {
    if (!room || settingUpRoom) return;
    setSettingUpRoom(room);
    try {
      await api.post("/kiosks", { name: room, room, zone: "" });
      toast.success(`Room ${room} is set up — Enter room is now available.`);
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not set up the room");
    } finally {
      setSettingUpRoom(null);
    }
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Residents</h2>
        <Button onClick={open_new} className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-resident-btn">
          <Plus className="w-4 h-4 mr-2" /> Add resident
        </Button>
      </div>
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
                    <Button variant="ghost" size="sm" onClick={() => setRecordFor(r)} data-testid={`record-res-${r.resident_id}`} title="Resident Record — conversations">
                      <BookOpen className="w-4 h-4 mr-1" /> Resident Record
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setMemoryFor(r)} data-testid={`mem-res-${r.resident_id}`}>Memory</Button>
                    <Button variant="ghost" size="sm" onClick={() => setMovementFor(r)} data-testid={`move-res-${r.resident_id}`}>Movement</Button>
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
      <ResidentFormDialog open={formOpen} onOpenChange={setFormOpen} resident={editingResident} kiosks={kiosks} onSaved={onChange} />
      <MovementDialog resident={movementFor} open={!!movementFor} onOpenChange={(o) => { if (!o) setMovementFor(null); }} />
      <MemoryDialog resident={memoryFor} open={!!memoryFor} onOpenChange={(o) => { if (!o) setMemoryFor(null); }} />
      <ResidentRecordDialog resident={recordFor} open={!!recordFor} onOpenChange={(o) => { if (!o) setRecordFor(null); }} />
    </Card>
  );
}
