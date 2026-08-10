import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Trash2, Pin, PinOff, Plus, Sparkles, MessageSquare } from "lucide-react";
import { toast } from "sonner";

const CATEGORIES = ["family", "preferences", "health", "history", "daily_pattern", "concern", "relationship", "milestone", "other"];
const CAT_COLOR = {
  family: "#4A7C59", preferences: "#D28D38", health: "#B6463A",
  history: "#8B5A20", daily_pattern: "#2F5940", concern: "#98392F",
  relationship: "#4A7C59", milestone: "#D28D38", other: "#7A6B56",
};

function fmt(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
  catch { return iso; }
}

export default function MemoryDialog({ resident, open, onOpenChange }) {
  const [memories, setMemories] = useState([]);
  const [conv, setConv] = useState([]);
  const [requests, setRequests] = useState([]);
  const [tab, setTab] = useState("memories");
  const [form, setForm] = useState({ text: "", category: "other", importance: 3, pinned: false });
  const [addOpen, setAddOpen] = useState(false);

  const fetchAll = async () => {
    if (!resident?.resident_id) return;
    try {
      const [mRes, cRes, rRes] = await Promise.all([
        api.get(`/memory/${resident.resident_id}`),
        api.get(`/memory/conversation/${resident.resident_id}`, { params: { limit: 100 } }).catch(() => ({ data: [] })),
        api.get(`/tasks`, { params: { resident_id: resident.resident_id } }).catch(() => ({ data: [] })),
      ]);
      setMemories(mRes.data);
      setConv(cRes.data);
      setRequests(rRes.data);
    } catch { toast.error("Could not load memory"); }
  };

  useEffect(() => { if (open) fetchAll(); }, [open, resident?.resident_id]);

  const addMemory = async (e) => {
    e.preventDefault();
    try {
      await api.post("/memory", { ...form, resident_id: resident.resident_id, source: "admin" });
      toast.success("Memory saved");
      setForm({ text: "", category: "other", importance: 3, pinned: false });
      setAddOpen(false);
      fetchAll();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const togglePin = async (m) => {
    try {
      await api.patch(`/memory/${m.memory_id}`, { pinned: !m.pinned });
      fetchAll();
    } catch { toast.error("Could not update"); }
  };

  const setImportance = async (m, importance) => {
    try {
      await api.patch(`/memory/${m.memory_id}`, { importance });
      fetchAll();
    } catch { toast.error("Could not update"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this memory? CAOS will forget it permanently.")) return;
    await api.delete(`/memory/${id}`);
    toast.success("Forgotten");
    fetchAll();
  };

  const pinned = memories.filter((m) => m.pinned);
  const unpinned = memories.filter((m) => !m.pinned);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="memory-dialog">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-caos-forest" />
            What CAOS knows about {resident?.preferred_name || resident?.name}
          </DialogTitle>
          <DialogDescription>
            Long-term memories and conversation log. Pin facts you want always present in context.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="memories" data-testid="mem-tab-memories">
              Memories ({memories.length})
            </TabsTrigger>
            <TabsTrigger value="conversation" data-testid="mem-tab-conversation">
              Conversation ({conv.length})
            </TabsTrigger>
            <TabsTrigger value="requests" data-testid="mem-tab-requests">
              Requests ({requests.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="memories" className="mt-4 space-y-4">
            <div className="flex justify-end">
              <Button onClick={() => setAddOpen(!addOpen)} className="rounded-full bg-caos-forest" data-testid="mem-add-toggle">
                <Plus className="w-4 h-4 mr-2" /> {addOpen ? "Cancel" : "Teach CAOS something"}
              </Button>
            </div>

            {addOpen && (
              <form onSubmit={addMemory} className="bg-caos-ambient rounded-2xl p-4 space-y-3 border border-caos-line" data-testid="mem-add-form">
                <div>
                  <Label>Memory</Label>
                  <Textarea
                    required
                    data-testid="mem-text"
                    value={form.text}
                    onChange={(e) => setForm({ ...form, text: e.target.value })}
                    placeholder="Her late husband Frank used to whistle Elvis tunes when he cooked."
                    rows={2}
                  />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label>Category</Label>
                    <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                      <SelectTrigger data-testid="mem-cat"><SelectValue /></SelectTrigger>
                      <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c.replace("_", " ")}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Importance (1-5)</Label>
                    <Input
                      type="number" min={1} max={5} required data-testid="mem-importance"
                      value={form.importance}
                      onChange={(e) => setForm({ ...form, importance: parseInt(e.target.value || "3", 10) })}
                    />
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-caos-forest" data-testid="mem-pinned-toggle">
                      <input type="checkbox" checked={form.pinned} onChange={(e) => setForm({ ...form, pinned: e.target.checked })} />
                      Pin to context
                    </label>
                  </div>
                </div>
                <Button type="submit" className="bg-caos-forest" data-testid="mem-save">Save memory</Button>
              </form>
            )}

            {pinned.length > 0 && (
              <div data-testid="mem-pinned-section">
                <p className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">★ Pinned — always in context</p>
                <div className="space-y-2">
                  {pinned.map((m) => <MemoryCard key={m.memory_id} m={m} onPin={togglePin} onDel={remove} onImp={setImportance} />)}
                </div>
              </div>
            )}

            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">All memories</p>
              <div className="space-y-2">
                {unpinned.map((m) => <MemoryCard key={m.memory_id} m={m} onPin={togglePin} onDel={remove} onImp={setImportance} />)}
                {memories.length === 0 && (
                  <p className="text-caos-mute italic py-6 text-center">CAOS hasn't learned anything yet. Their first conversation will start filling this up.</p>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="conversation" className="mt-4">
            <div className="max-h-[55vh] overflow-y-auto bg-white rounded-2xl border border-caos-line p-4 space-y-3">
              {conv.map((m) => (
                <div key={m.conv_id || m.created_at} data-testid={`conv-${m.role}`} className={`text-sm ${m.role === "user" ? "text-caos-ink/80" : "text-caos-forest font-medium"}`}>
                  <span className="text-[10px] uppercase tracking-widest text-caos-mute mr-2">{m.role === "user" ? "Resident" : "CAOS"}</span>
                  {m.content}
                </div>
              ))}
              {conv.length === 0 && (
                <p className="text-caos-mute italic text-center py-6">No conversation logged yet.</p>
              )}
            </div>
            <p className="text-xs text-caos-mute mt-2 flex items-center gap-1">
              <MessageSquare className="w-3 h-3" /> Only selected recent context is used by the configured conversation service, but the full transcript is archived here.
            </p>
          </TabsContent>

          <TabsContent value="requests" className="mt-4 space-y-2">
            {requests.map((r) => (
              <div key={r.task_id} className="bg-white border border-caos-line rounded-2xl p-3" data-testid={`req-${r.task_id}`}>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="font-medium text-caos-forest">{r.title}</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] uppercase tracking-wider">{r.category}</Badge>
                    <Badge className="text-[10px] uppercase tracking-wider">{r.status}</Badge>
                  </div>
                </div>
                {r.resident_words && (
                  <p className="text-sm text-caos-ink/70 italic mt-1">"{r.resident_words}"</p>
                )}
                <p className="text-[10px] text-caos-mute uppercase tracking-wider mt-1">
                  {r.source} · {fmt(r.created_at)}
                  {r.assigned_name ? ` · assigned to ${r.assigned_name}` : ""}
                </p>
              </div>
            ))}
            {requests.length === 0 && (
              <p className="text-caos-mute italic text-center py-6">No staff requests (nursing/maintenance/kitchen/etc.) on record for this resident.</p>
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

function MemoryCard({ m, onPin, onDel, onImp }) {
  const color = CAT_COLOR[m.category] || "#7A6B56";
  return (
    <div className="bg-white border border-caos-line rounded-2xl p-3 flex items-start gap-3" data-testid={`mem-card-${m.memory_id}`}>
      <div className="shrink-0 mt-1">
        <span
          className="inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: color }}
          title={m.category}
        />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-caos-forest leading-snug">{m.text}</p>
        <div className="flex gap-2 mt-1 items-center flex-wrap">
          <Badge variant="outline" className="text-[10px] uppercase tracking-wider">{m.category?.replace("_", " ")}</Badge>
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                onClick={() => onImp(m, n)}
                data-testid={`mem-imp-${m.memory_id}-${n}`}
                className={`w-4 h-4 rounded-full border-2 ${n <= m.importance ? "bg-caos-forest border-caos-forest" : "bg-transparent border-caos-line"}`}
                title={`Importance ${n}`}
              />
            ))}
          </div>
          <span className="text-[10px] text-caos-mute uppercase tracking-wider">
            {m.source} · {fmt(m.created_at)}
            {m.times_referenced ? ` · referenced ${m.times_referenced}×` : ""}
          </span>
        </div>
      </div>
      <div className="flex gap-1 shrink-0">
        <Button variant="ghost" size="sm" onClick={() => onPin(m)} data-testid={`mem-pin-${m.memory_id}`} title={m.pinned ? "Unpin" : "Pin"}>
          {m.pinned ? <PinOff className="w-4 h-4 text-caos-amber" /> : <Pin className="w-4 h-4 text-caos-mute" />}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDel(m.memory_id)} data-testid={`mem-del-${m.memory_id}`}>
          <Trash2 className="w-4 h-4 text-caos-terracotta" />
        </Button>
      </div>
    </div>
  );
}
