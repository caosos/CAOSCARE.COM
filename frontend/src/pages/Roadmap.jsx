import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { CheckCircle2, Circle, Clock, Ban, Pencil, X } from "lucide-react";
import { toast } from "sonner";

const STATUS_META = {
  done: { label: "Shipped", color: "#4A7C59", bg: "#EAF3EC", icon: CheckCircle2 },
  in_progress: { label: "In progress", color: "#D28D38", bg: "#FDF3E3", icon: Clock },
  not_started: { label: "Not started", color: "#6B726A", bg: "#EAE7DF", icon: Circle },
  blocked: { label: "Blocked", color: "#B6463A", bg: "#FDECE9", icon: Ban },
};

const PHASE_TITLES = {
  1: "Phase 1 — Core Pilot",
  2: "Phase 2 — Workflow Visibility",
  3: "Phase 3 — Location & Mobility",
  4: "Phase 4 — Predictive Insight",
  5: "Cross-cutting Infrastructure",
};

export default function Roadmap() {
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null); // item_id
  const [editNotes, setEditNotes] = useState("");

  const fetchItems = async () => {
    try {
      const { data } = await api.get("/roadmap");
      setItems(data);
    } catch {
      toast.error("Could not load roadmap");
    }
  };

  useEffect(() => { fetchItems(); }, []);

  const updateStatus = async (item, status) => {
    try {
      await api.patch(`/roadmap/${item.item_id}`, { status });
      toast.success("Updated");
      fetchItems();
    } catch {
      toast.error("Failed");
    }
  };

  const saveNotes = async (item) => {
    try {
      await api.patch(`/roadmap/${item.item_id}`, { notes: editNotes });
      setEditing(null);
      setEditNotes("");
      toast.success("Notes saved");
      fetchItems();
    } catch {
      toast.error("Failed");
    }
  };

  // Group by phase
  const byPhase = {};
  items.forEach((it) => {
    byPhase[it.phase] = byPhase[it.phase] || [];
    byPhase[it.phase].push(it);
  });

  const progressFor = (phase) => {
    const arr = byPhase[phase] || [];
    if (!arr.length) return 0;
    return Math.round((arr.filter((i) => i.status === "done").length / arr.length) * 100);
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-display text-2xl font-medium text-caos-forest">Phase-build checklist</h2>
        <p className="text-caos-mute mt-1">
          Every item from your blueprint. Click a status to update. Click the pencil to add notes.
        </p>
      </div>

      <div className="space-y-8">
        {Object.keys(PHASE_TITLES).map((phase) => {
          const list = byPhase[phase] || [];
          if (list.length === 0) return null;
          const pct = progressFor(phase);
          return (
            <section key={phase} data-testid={`roadmap-phase-${phase}`}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-display text-xl font-medium text-caos-forest">{PHASE_TITLES[phase]}</h3>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-caos-mute font-mono">{pct}%</span>
                  <div className="w-32 h-1.5 bg-caos-ambient rounded-full overflow-hidden">
                    <div
                      className="h-full bg-caos-forest transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {list.map((item) => {
                  const meta = STATUS_META[item.status] || STATUS_META.not_started;
                  const Icon = meta.icon;
                  const isEditing = editing === item.item_id;
                  return (
                    <Card
                      key={item.item_id}
                      data-testid={`roadmap-item-${item.item_id}`}
                      className="p-4 border-caos-line bg-white hover:border-caos-forest/40 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <Icon className="w-5 h-5 mt-1 shrink-0" style={{ color: meta.color }} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p className="font-semibold text-caos-forest">{item.title}</p>
                            <Badge
                              style={{ background: meta.bg, color: meta.color, border: `1px solid ${meta.color}33` }}
                              className="uppercase text-xs tracking-wider font-bold shrink-0"
                            >
                              {meta.label}
                            </Badge>
                          </div>
                          {item.description && (
                            <p className="text-caos-mute text-sm mt-1">{item.description}</p>
                          )}
                          {item.notes && !isEditing && (
                            <div className="mt-2 bg-caos-ambient rounded-lg px-3 py-2 text-sm text-caos-ink/80 border-l-2 border-caos-forest">
                              {item.notes}
                            </div>
                          )}
                          {isEditing && (
                            <div className="mt-2">
                              <Textarea
                                value={editNotes}
                                onChange={(e) => setEditNotes(e.target.value)}
                                placeholder="Add notes, blockers, or decisions…"
                                data-testid={`roadmap-notes-${item.item_id}`}
                              />
                              <div className="flex gap-2 mt-2">
                                <Button size="sm" onClick={() => saveNotes(item)} className="bg-caos-forest" data-testid={`roadmap-save-${item.item_id}`}>
                                  Save
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => { setEditing(null); setEditNotes(""); }}>
                                  <X className="w-4 h-4" />
                                </Button>
                              </div>
                            </div>
                          )}
                          <div className="flex items-center gap-2 mt-3">
                            <Select value={item.status} onValueChange={(v) => updateStatus(item, v)}>
                              <SelectTrigger className="w-[140px] h-8 text-xs" data-testid={`roadmap-status-${item.item_id}`}>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="not_started">Not started</SelectItem>
                                <SelectItem value="in_progress">In progress</SelectItem>
                                <SelectItem value="done">Shipped</SelectItem>
                                <SelectItem value="blocked">Blocked</SelectItem>
                              </SelectContent>
                            </Select>
                            {!isEditing && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => { setEditing(item.item_id); setEditNotes(item.notes || ""); }}
                                data-testid={`roadmap-edit-${item.item_id}`}
                                className="h-8"
                              >
                                <Pencil className="w-3.5 h-3.5 mr-1" /> Notes
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
