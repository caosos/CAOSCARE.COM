import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen, DoorOpen, Pencil, Plus, Search, Trash2, Volume2 } from "lucide-react";
import { api } from "../lib/api";
import { useResidentActions } from "../lib/useResidentActions";
import WorkspaceShell from "../components/workspace/WorkspaceShell";
import ResidentRecordDialog from "./ResidentRecordDialog";
import ResidentFormDialog from "./ResidentFormDialog";

const PARTICIPATION = { room_only: "Room only", pendant_enhanced: "Pendant", wearable_enhanced: "Wearable", family_connected: "Family connected", full: "Full" };   // models.ParticipationLevel
const initials = (n) => (n || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");

function IconAction({ label, onClick, children, tone = "text-[#374151]", testid, disabled }) {
  return (
    <button type="button" onClick={onClick} title={label} aria-label={label} data-testid={testid} disabled={disabled}
            className={`rounded-md p-2 hover:bg-[#F3F4F6] disabled:opacity-40 ${tone}`}>
      {children}
    </button>
  );
}

// Residents in the Live Operations design (same shell as the dashboard).
// Same records and actions as the classic Residents tab: resident hub
// (overview, conversations, assistance events, requests, memory, movement,
// device), add/edit, enter or set up the room, spoken briefing, delete.
export default function ResidentsPage() {
  const [residents, setResidents] = useState(null);
  const [kiosks, setKiosks] = useState([]);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [recordFor, setRecordFor] = useState(null);
  const [sp, setSp] = useSearchParams();

  const load = useCallback(async () => {
    try {
      const [r, k] = await Promise.all([api.get("/residents"), api.get("/kiosks")]);
      setResidents(r.data); setKiosks(k.data); setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not load residents");
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  // /residents?resident=<id> opens that resident's hub (links from cards, Aria).
  useEffect(() => {
    const id = sp.get("resident");
    if (!id || !residents) return;
    const r = residents.find((x) => x.resident_id === id);
    if (r) setRecordFor(r);
  }, [sp, residents]);
  const openRecord = (r) => { setRecordFor(r); setSp((p) => { const n = new URLSearchParams(p); n.set("resident", r.resident_id); return n; }); };
  const closeRecord = () => { setRecordFor(null); setSp((p) => { const n = new URLSearchParams(p); n.delete("resident"); return n; }); };

  const { kioskForRoom, enterRoom, setUpRoom, settingUpRoom, speakBriefing, briefingId, remove } =
    useResidentActions({ kiosks, onChange: load });

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (residents || []).filter((r) => {
      if (filter === "no_room_screen" && kioskForRoom(r.room)) return false;
      if (filter !== "all" && filter !== "no_room_screen" && r.participation_level !== filter) return false;
      if (!needle) return true;
      return [r.name, r.preferred_name, r.room, r.pendant_id].some((v) => (v || "").toLowerCase().includes(needle));
    });
  }, [residents, q, filter, kiosks]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <WorkspaceShell crumbs={[{ label: "Residents" }]}>
      <div className="mt-1 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-bold leading-tight tracking-tight sm:text-[36px]">Residents</h1>
          <p className="mt-1 text-[17px] text-[#4B5563] sm:text-[20px]">
            {residents ? `${residents.length} resident${residents.length === 1 ? "" : "s"}` : "Loading…"} · rooms, care profiles and requests
          </p>
        </div>
        <button type="button" onClick={() => { setEditing(null); setFormOpen(true); }} data-testid="add-resident-btn"
                className="flex items-center gap-2 rounded-lg bg-[#2F80ED] px-5 py-3 text-[16px] font-medium text-white shadow-sm hover:bg-[#1F6FD9]">
          <Plus className="h-5 w-5" /> Add resident
        </button>
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <label className="flex flex-1 items-center gap-2 rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5">
          <Search className="h-4 w-4 text-[#9CA3AF]" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, room or pendant"
                 aria-label="Search residents" data-testid="residents-search" className="w-full bg-transparent text-[15px] outline-none" />
        </label>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter residents"
                className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5 text-[15px]">
          <option value="all">All residents</option>
          {Object.entries(PARTICIPATION).map(([v, l]) => <option key={v} value={v}>Participation: {l}</option>)}
          <option value="no_room_screen">No room screen set up</option>
        </select>
      </div>

      {error && <p className="mt-4 text-[#B42318]">{error}</p>}
      <div className="mt-4 overflow-hidden rounded-2xl border border-[#E5E7EB] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        <ul className="divide-y divide-[#F3F4F6]" data-testid="residents-list">
          {shown.map((r) => {
            const kiosk = kioskForRoom(r.room);
            return (
              <li key={r.resident_id} data-testid={`res-row-${r.resident_id}`}
                  className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center">
                <button type="button" onClick={() => openRecord(r)} className="flex min-w-0 flex-1 items-center gap-4 text-left"
                        data-testid={`record-res-${r.resident_id}`}>
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#FFF3D6] text-[15px] font-semibold text-[#B7791F]">
                    {initials(r.name)}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[16px] font-semibold text-[#111827]">
                      {r.name}{r.preferred_name ? <span className="font-normal text-[#6B7280]"> · “{r.preferred_name}”</span> : null}
                    </span>
                    <span className="block text-[14px] text-[#4B5563]">
                      Room {r.room || "—"}{r.pendant_id ? ` · Pendant ${r.pendant_id}` : ""}
                      {r.participation_level ? ` · ${PARTICIPATION[r.participation_level] || r.participation_level}` : ""}
                    </span>
                  </span>
                </button>
                <div className="flex flex-wrap items-center gap-1">
                  <button type="button" onClick={() => openRecord(r)}
                          className="flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-[14px] font-medium hover:bg-[#F9FAFB]">
                    <BookOpen className="h-4 w-4" /> Resident hub
                  </button>
                  {kiosk ? (
                    <IconAction label={`Enter ${r.name}'s room screen`} onClick={() => enterRoom(r)} testid={`enter-room-${r.resident_id}`}>
                      <DoorOpen className="h-[18px] w-[18px]" />
                    </IconAction>
                  ) : (
                    <button type="button" onClick={() => setUpRoom(r.room)} disabled={settingUpRoom === r.room}
                            data-testid={`setup-room-${r.resident_id}`}
                            className="rounded-lg px-3 py-2 text-[14px] text-[#B45309] hover:bg-[#FFF7ED] disabled:opacity-50">
                      {settingUpRoom === r.room ? "Setting up…" : "Set up room"}
                    </button>
                  )}
                  <IconAction label={briefingId === r.resident_id ? "Speaking briefing" : "Speak a briefing"}
                              onClick={() => speakBriefing(r)} testid={`brief-res-${r.resident_id}`}
                              tone={briefingId === r.resident_id ? "text-[#2F80ED]" : "text-[#374151]"}>
                    <Volume2 className={`h-[18px] w-[18px] ${briefingId === r.resident_id ? "animate-pulse" : ""}`} />
                  </IconAction>
                  <IconAction label={`Edit ${r.name}`} onClick={() => { setEditing(r); setFormOpen(true); }} testid={`edit-res-${r.resident_id}`}>
                    <Pencil className="h-[18px] w-[18px]" />
                  </IconAction>
                  <IconAction label={`Delete ${r.name}`} onClick={() => remove(r.resident_id)} tone="text-[#B42318]" testid={`del-res-${r.resident_id}`}>
                    <Trash2 className="h-[18px] w-[18px]" />
                  </IconAction>
                </div>
              </li>
            );
          })}
          {residents && !shown.length && (
            <li className="px-5 py-10 text-center text-[#6B7280]">{residents.length ? "No residents match." : "No residents yet."}</li>
          )}
        </ul>
      </div>
      <ResidentFormDialog open={formOpen} onOpenChange={setFormOpen} resident={editing} kiosks={kiosks} onSaved={load} />
      <ResidentRecordDialog resident={recordFor} open={!!recordFor} onOpenChange={(o) => { if (!o) closeRecord(); }} />
    </WorkspaceShell>
  );
}
