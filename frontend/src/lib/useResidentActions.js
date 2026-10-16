// Resident row actions shared by the classic Residents tab and the new
// Residents page (moved out of ResidentsTab.jsx unchanged): enter the room's
// screen, set up the room's kiosk record, speak a briefing, delete.
import { useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "./api";

export function useResidentActions({ kiosks, onChange }) {
  const [briefingId, setBriefingId] = useState(null);   // resident_id currently speaking
  const [settingUpRoom, setSettingUpRoom] = useState(null);   // room currently being set up
  const audioRef = useRef(null);

  // The resident<->kiosk link is a room-string match (Kiosk.room === Resident.room),
  // the same lookup /residents/public/by-kiosk/{id} does server-side.
  const kioskForRoom = (room) => (kiosks || []).find((k) => k.room === room);

  const enterRoom = (r) => {
    const kiosk = kioskForRoom(r.room);
    if (!kiosk) {
      toast.error(`No kiosk mapped to room "${r.room}" — nothing to open.`);
      return;
    }
    window.open(`/kiosk/${kiosk.kiosk_id}`, "_blank", "noopener");
  };

  // Creates the real logical kiosk record for this room via the same POST
  // /kiosks Admin -> Kiosks uses; Enter room then resolves it immediately.
  const setUpRoom = async (room) => {
    if (!room || settingUpRoom) return;
    setSettingUpRoom(room);
    try {
      await api.post("/kiosks", { name: room, room, zone: "" });
      toast.success(`Room ${room} is set up — Enter room is now available.`);
      onChange?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not set up the room");
    } finally {
      setSettingUpRoom(null);
    }
  };

  // Voice briefing: the resident's narrative read aloud through the TTS route.
  const speakBriefing = async (r) => {
    try {
      if (audioRef.current) { try { audioRef.current.pause(); } catch { /* already stopped */ } audioRef.current = null; }
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

  const remove = async (id) => {
    if (!window.confirm("Delete this resident?")) return;
    await api.delete(`/residents/${id}`);
    toast.success("Deleted");
    onChange?.();
  };

  return { kioskForRoom, enterRoom, setUpRoom, settingUpRoom, speakBriefing, briefingId, remove };
}
