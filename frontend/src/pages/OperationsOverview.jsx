import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { RefreshCw, ChevronRight, AlertCircle, Info } from "lucide-react";
import { toast } from "sonner";
import { formatAge, attentionAccent, accentStyle, linkTarget } from "../lib/opsOverview";

// Admin / ED operations overview. Read-only. Every value comes from
// GET /ops/overview (routes/ops_overview.py), which derives it live from
// the existing staff_tasks / alerts / departments / transport records -
// this component only lays it out. Rendered as the default Admin tab;
// `onNavigate` switches to a sibling tab, route links go to the alert board.

export default function OperationsOverview({ onNavigate }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const { data: d } = await api.get("/ops/overview");
      setData(d);
    } catch {
      toast.error("Could not load the operations overview");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const go = (hint) => {
    const t = linkTarget(hint);
    if (t.type === "route") navigate(t.value);
    else onNavigate?.(t.value);
  };

  if (loading && !data) return <Card className="border-caos-line p-8 text-caos-mute">Loading operations overview…</Card>;
  if (!data) return null;

  const { attention, attention_total, departments, assistance, tasks, transportation } = data;

  return (
    <div className="space-y-8" data-testid="ops-overview">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display text-2xl font-medium text-caos-forest">Operations overview</h2>
          <p className="text-caos-mute text-sm mt-1">
            What needs attention, what's waiting, what's overdue, who owns it — for {data.facility_date}.
          </p>
        </div>
        <Button variant="ghost" onClick={load} data-testid="ops-refresh"><RefreshCw className="w-4 h-4 mr-2" /> Refresh</Button>
      </div>

      {/* 1. NEEDS ATTENTION NOW */}
      <section>
        <SectionHead
          title="Needs attention now"
          right={attention_total > attention.length ? `showing ${attention.length} of ${attention_total}` : `${attention.length}`}
        />
        <div className="space-y-2" data-testid="ops-attention-list">
          {attention.length === 0 && (
            <Card className="p-8 text-center border-caos-line text-caos-mute italic" data-testid="ops-attention-empty">
              Nothing needs attention right now.
            </Card>
          )}
          {attention.map((it) => {
            const c = accentStyle(attentionAccent(it));
            return (
              <Card
                key={`${it.kind}-${it.ref_id}`}
                data-testid={`ops-attention-row-${it.ref_id}`}
                className="p-4 border-2 cursor-pointer hover:shadow-sm transition-shadow"
                style={{ borderLeftColor: c.border, borderLeftWidth: 6 }}
                onClick={() => go(it.link_hint)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }} className="uppercase tracking-wider text-[10px] font-bold">
                        {it.reason}
                      </Badge>
                      {it.severity && <Badge variant="outline" className="uppercase text-[10px]">{it.severity}</Badge>}
                      {it.priority && it.priority !== "normal" && <Badge variant="outline" className="uppercase text-[10px]">{it.priority}</Badge>}
                      <span className="text-caos-mute text-xs">open {formatAge(it.age_seconds)}</span>
                    </div>
                    <div className="font-semibold text-caos-forest mt-1 truncate">{it.title}</div>
                    <div className="text-xs text-caos-mute mt-0.5">
                      {[
                        it.room ? `Room ${it.room}` : null,
                        it.resident_name,
                        it.department,
                        it.owner ? `owner: ${it.owner}` : "unowned",
                        it.status,
                      ].filter(Boolean).join(" · ")}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-caos-mute shrink-0 mt-1" />
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* 2. DEPARTMENT STATUS */}
      <section>
        <SectionHead title="Department status" right={`${departments.length}`} />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="ops-departments">
          {departments.map((d) => (
            <Card key={d.slug} className="p-4 border-caos-line" data-testid={`ops-dept-${d.slug}`}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-caos-forest">{d.label}</span>
                {!d.active && <Badge variant="outline" className="text-[10px] text-caos-mute">inactive</Badge>}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                <Stat n={d.open} label="open" />
                <Stat n={d.overdue} label="overdue" warn={d.overdue > 0} />
                <Stat n={d.unassigned} label="no owner" warn={d.unassigned > 0} />
                <Stat n={d.in_progress} label="in progress" />
                <Stat n={d.completed_today} label="done today" />
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* 3. RESIDENT ASSISTANCE SUMMARY (read-only) */}
      <section>
        <SectionHead
          title="Resident assistance"
          right={<span className="text-caos-mute text-xs uppercase tracking-wider">read-only</span>}
        />
        <Card className="p-5 border-caos-line" data-testid="ops-assistance">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat n={assistance.active} label="active (unacked)" warn={assistance.active > 0} />
            <Stat n={assistance.acknowledged} label="acknowledged" />
            <Stat n={assistance.resolved_today} label="resolved today" />
            <Stat n={assistance.open_total} label="open total" />
            <Stat n={assistance.unowned_open} label="open, no owner" warn={assistance.unowned_open > 0} />
            <Stat n={assistance.owned_open} label="open, owned" />
            <Stat n={assistance.aging_open_gt_2h} label="open > 2h" />
            <Stat n={assistance.aging_open_gt_24h} label="open > 24h" />
          </div>
          {assistance.oldest_open && (
            <div className="mt-4 text-sm text-caos-ink/80">
              Oldest open:{" "}
              <strong>{assistance.oldest_open.resident_name || "Unknown"}</strong>
              {assistance.oldest_open.room ? ` · Room ${assistance.oldest_open.room}` : ""}
              {" · "}{assistance.oldest_open.severity}
              {" · "}open {assistance.oldest_open.minutes_open} min ({assistance.oldest_open.status})
            </div>
          )}
          {assistance.possibly_stale_open_gt_72h > 0 && (
            <div className="mt-3 flex items-start gap-2 text-xs text-caos-mute bg-[#F3F1EE] rounded-lg p-3" data-testid="ops-assistance-stale">
              <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>
                {assistance.possibly_stale_open_gt_72h} open event{assistance.possibly_stale_open_gt_72h === 1 ? "" : "s"} older than{" "}
                {assistance.stale_threshold_hours}h — likely stale RF/pendant test activations, not a live queue.
                Not cleaned up in this pass.
              </span>
            </div>
          )}
          <div className="mt-3">
            <Button variant="outline" size="sm" className="border-2" onClick={() => navigate("/staff")} data-testid="ops-assistance-link">
              Open the alert board <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </Card>
      </section>

      {/* 4. TASK OWNERSHIP / AGING */}
      <section>
        <SectionHead
          title="Task ownership & aging"
          right={`${tasks.open_total} open · ${tasks.unassigned_open} no owner · ${tasks.overdue_open} overdue`}
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TaskList title="No owner" rows={tasks.unassigned} onOpen={go} emptyText="Everything open has an owner." />
          <TaskList title="Sitting longest" rows={tasks.oldest_open} onOpen={go} emptyText="No open tasks." />
        </div>
      </section>

      {/* 5. TRANSPORTATION */}
      <section>
        <SectionHead title="Transportation — today" right={transportation.date} />
        <Card className="p-5 border-caos-line" data-testid="ops-transportation">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center">
            <Stat n={transportation.requests_today} label="requests today" />
            <Stat n={transportation.open} label="open" />
            <Stat n={transportation.booked_open} label="booked" />
            <Stat n={transportation.needs_action} label="needs a slot" warn={transportation.needs_action > 0} />
            <Stat n={transportation.past_requested_date_open} label="past date" warn={transportation.past_requested_date_open > 0} />
            <Stat n={transportation.completed_today} label="done today" />
          </div>
          {transportation.waiting_unbooked.length > 0 && (
            <div className="mt-3 text-xs text-caos-mute">
              Waiting on a slot: {transportation.waiting_unbooked.map((r) => r.room || r.task_id).join(", ")}
            </div>
          )}
          <div className="mt-3">
            <Button variant="outline" size="sm" className="border-2" onClick={() => onNavigate?.("transportation")} data-testid="ops-transportation-link">
              Open transportation <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </Card>
      </section>

      <p className="text-xs text-caos-mute italic flex items-start gap-2">
        <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {data.counts_caveat}
      </p>
    </div>
  );
}

function SectionHead({ title, right }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h3 className="font-display text-xl font-medium text-caos-forest">{title}</h3>
      {right != null && <span className="text-sm text-caos-mute">{right}</span>}
    </div>
  );
}

function Stat({ n, label, warn }) {
  return (
    <div className="rounded-xl border border-caos-line p-2">
      <div className={`text-2xl font-display ${warn ? "text-caos-terracotta" : "text-caos-forest"}`}>{n}</div>
      <div className="text-[10px] uppercase tracking-wider text-caos-mute">{label}</div>
    </div>
  );
}

function TaskList({ title, rows, onOpen, emptyText }) {
  return (
    <Card className="p-4 border-caos-line" data-testid={`ops-tasklist-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <div className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">{title}</div>
      {rows.length === 0 && <div className="text-caos-mute text-sm italic py-3">{emptyText}</div>}
      <div className="space-y-1">
        {rows.map((t) => (
          <button
            key={t.task_id}
            onClick={() => onOpen(t.link_hint)}
            data-testid={`ops-task-${t.task_id}`}
            className="w-full text-left rounded-lg border border-caos-line p-2 hover:border-caos-forest transition-colors"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-sm text-caos-forest truncate">{t.title}</span>
              <span className="text-xs text-caos-mute shrink-0">{formatAge(t.age_seconds)}</span>
            </div>
            <div className="text-[11px] text-caos-mute mt-0.5">
              {[t.department, t.room ? `Room ${t.room}` : null, t.assigned_name || "no owner", t.status].filter(Boolean).join(" · ")}
              {t.overdue && <span className="text-caos-terracotta font-semibold"> · overdue</span>}
              {t.re_request_count > 0 && <span className="text-caos-terracotta"> · asked {t.re_request_count}×</span>}
            </div>
          </button>
        ))}
      </div>
    </Card>
  );
}
