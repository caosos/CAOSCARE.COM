import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import { callState, callKind, wasConnected } from "../lib/callState";

// Phone extensions on the local Asterisk (must match its configuration)
// and the call log. Call states are exactly what Asterisk reported.
export default function PhoneCallsPanel() {
  const [endpoints, setEndpoints] = useState([]);
  const [calls, setCalls] = useState([]);
  const [form, setForm] = useState({ extension: "", kind: "room", room: "", label: "" });

  const load = async () => {
    try {
      const [e, c] = await Promise.all([api.get("/telephony/endpoints"), api.get("/telephony/calls?limit=50")]);
      setEndpoints(e.data);
      setCalls(c.data);
    } catch {
      toast.error("Could not load phones");
    }
  };
  useEffect(() => { load(); }, []);

  const add = async (ev) => {
    ev.preventDefault();
    try {
      await api.post("/telephony/endpoints", { ...form, room: form.kind === "room" ? form.room : null });
      toast.success("Extension added");
      setForm({ extension: "", kind: "room", room: "", label: "" });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail?.toString() || "Could not add extension");
    }
  };

  const retire = async (id) => {
    await api.delete(`/telephony/endpoints/${id}`);
    load();
  };

  return (
    <div className="space-y-6">
      <Card className="border-caos-line p-5">
        <h3 className="font-display text-lg font-medium text-caos-forest">Phone extensions</h3>
        <p className="text-caos-mute text-sm mt-1 mb-4">
          Room handsets, the front desk phone and Aria on the local phone system. Dial 0 and 911 are
          handled by the phone system itself and work without CAOSCare.
        </p>
        <form onSubmit={add} className="flex flex-wrap gap-2 items-end mb-4" data-testid="phone-ext-form">
          <Input required className="w-28" placeholder="Extension" value={form.extension}
            onChange={(e) => setForm({ ...form, extension: e.target.value })} />
          <Select value={form.kind} onValueChange={(v) => setForm({ ...form, kind: v })}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="room">Room handset</SelectItem>
              <SelectItem value="front_desk">Front desk</SelectItem>
              <SelectItem value="aria">Aria</SelectItem>
            </SelectContent>
          </Select>
          {form.kind === "room" && (
            <Input required className="w-28" placeholder="Room" value={form.room}
              onChange={(e) => setForm({ ...form, room: e.target.value })} />
          )}
          <Input className="w-48" placeholder="Label (optional)" value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })} />
          <Button type="submit" className="bg-caos-forest rounded-full"><Plus className="w-4 h-4 mr-1" /> Add</Button>
        </form>
        {endpoints.map((e) => (
          <div key={e.endpoint_id} className="flex items-center gap-3 text-sm py-1">
            <span className="font-mono w-16">{e.extension}</span>
            <Badge variant="outline" className="text-xs">{e.kind === "room" ? `Room ${e.room}` : e.kind.replace("_", " ")}</Badge>
            <span className="text-caos-mute">{e.label}</span>
            <Button variant="ghost" size="sm" className="ml-auto" onClick={() => retire(e.endpoint_id)} aria-label="Retire extension">
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        ))}
        {endpoints.length === 0 && <p className="text-caos-mute text-sm">No extensions configured.</p>}
      </Card>

      <Card className="border-caos-line p-5">
        <h3 className="font-display text-lg font-medium text-caos-forest mb-3">Calls</h3>
        <div className="space-y-2" data-testid="call-log">
          {calls.map((c) => {
            const s = callState(c.state);
            return (
              <details key={c.call_id} className="p-3 bg-caos-ambient/40 rounded-lg text-sm">
                <summary className="flex flex-wrap items-center gap-2 cursor-pointer">
                  <Badge variant="outline" className="text-xs">{callKind(c.kind)}</Badge>
                  <span>{c.room ? `Room ${c.room}` : `Ext ${c.from_extension || "?"}`} → {c.target_label || callKind(c.kind)}</span>
                  <Badge variant="outline" className={`text-xs ${s.tone}`}>{s.label}</Badge>
                  {c.state === "ended" && <span className="text-xs text-caos-mute">{wasConnected(c) ? "was answered" : "never answered"}</span>}
                  <span className="text-xs text-caos-mute ml-auto">{c.created_at ? new Date(c.created_at).toLocaleString() : ""}</span>
                </summary>
                <ol className="mt-2 space-y-1 text-xs text-caos-mute">
                  {(c.history || []).map((h, i) => (
                    <li key={i}>{new Date(h.at).toLocaleTimeString()} · {callState(h.state).label} · {h.source}{h.detail ? ` · ${h.detail}` : ""}</li>
                  ))}
                </ol>
              </details>
            );
          })}
          {calls.length === 0 && <p className="text-caos-mute text-sm">No calls recorded.</p>}
        </div>
      </Card>
    </div>
  );
}
