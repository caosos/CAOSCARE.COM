import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { RefreshCw, TrendingUp, TrendingDown, Minus, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

const SEV_META = {
  concern: { color: "#B6463A", bg: "#FDECE9", label: "Concern" },
  watch: { color: "#D28D38", bg: "#FDF3E3", label: "Watch" },
  info: { color: "#4A7C59", bg: "#EAF3EC", label: "Info" },
};

export default function Insights() {
  const [items, setItems] = useState([]);
  const [computing, setComputing] = useState(false);

  const fetchItems = async () => {
    try {
      const { data } = await api.get("/insights");
      setItems(data);
    } catch { toast.error("Could not load insights"); }
  };
  useEffect(() => { fetchItems(); }, []);

  const compute = async () => {
    setComputing(true);
    try {
      const { data } = await api.post("/insights/compute");
      toast.success(`Computed ${data.computed} insights across ${data.residents} residents`);
      fetchItems();
    } catch { toast.error("Compute failed"); }
    finally { setComputing(false); }
  };

  // Group by resident
  const byResident = {};
  items.forEach((it) => {
    byResident[it.resident_name] = byResident[it.resident_name] || [];
    byResident[it.resident_name].push(it);
  });

  return (
    <div>
      <div className="flex justify-between items-start mb-6 flex-wrap gap-3">
        <div className="max-w-2xl">
          <h2 className="font-display text-2xl font-medium text-caos-forest">Pattern insights</h2>
          <p className="text-caos-mute mt-1">
            Non-diagnostic observations. Each flag compares the last 7 days to the prior 7 days per resident —
            help requests, nighttime activity, and zone mobility. Confidence scales with sample size.
          </p>
          <p className="text-caos-mute text-sm mt-2 italic">
            <AlertTriangle className="inline w-3.5 h-3.5 mr-1 -mt-0.5" />
            These are <b>signals for staff awareness</b>, not clinical diagnoses. Always pair with direct observation.
          </p>
        </div>
        <Button onClick={compute} disabled={computing} className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="compute-insights-btn">
          <RefreshCw className={`w-4 h-4 mr-2 ${computing ? "animate-spin" : ""}`} /> {computing ? "Computing…" : "Recompute"}
        </Button>
      </div>

      {items.length === 0 && (
        <Card className="p-10 text-center border-caos-line">
          <p className="font-display text-lg text-caos-forest">No insights yet.</p>
          <p className="text-caos-mute mt-1">Press Recompute to generate observations from the last 14 days of data.</p>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {items.map((it) => {
          const sev = SEV_META[it.severity] || SEV_META.info;
          const dir =
            it.current_value > it.baseline_value
              ? TrendingUp
              : it.current_value < it.baseline_value
              ? TrendingDown
              : Minus;
          const Dir = dir;
          return (
            <Card
              key={it.insight_id}
              data-testid={`insight-${it.insight_id}`}
              className="p-5 border-2 bg-white"
              style={{ borderLeftColor: sev.color, borderLeftWidth: 6 }}
            >
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge style={{ background: sev.bg, color: sev.color, border: `1px solid ${sev.color}33` }} className="uppercase tracking-wider font-bold">
                      {sev.label}
                    </Badge>
                    <Badge variant="outline" className="uppercase tracking-wider text-xs">
                      {it.metric.replace(/_/g, " ")}
                    </Badge>
                    <div className="text-xs text-caos-mute flex items-center gap-1">
                      confidence
                      <div className="w-16 h-1.5 bg-caos-ambient rounded-full overflow-hidden">
                        <div className="h-full bg-caos-forest" style={{ width: `${Math.round(it.confidence * 100)}%` }} />
                      </div>
                      <span className="font-mono">{Math.round(it.confidence * 100)}%</span>
                    </div>
                  </div>
                  <h3 className="font-display text-lg font-medium text-caos-forest mt-2 flex items-center gap-2">
                    <Dir className="w-5 h-5" style={{ color: sev.color }} />
                    {it.title}
                  </h3>
                  <p className="text-caos-mute text-sm mt-1">{it.description}</p>
                  <div className="mt-3 flex items-center gap-4 text-xs font-mono">
                    <div className="flex items-center gap-1.5">
                      <span className="text-caos-mute uppercase tracking-wider">7d</span>
                      <span className="text-caos-forest font-bold text-base">{it.current_value}</span>
                    </div>
                    <div className="text-caos-mute">vs</div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-caos-mute uppercase tracking-wider">prior 7d</span>
                      <span className="text-caos-ink font-bold text-base">{it.baseline_value}</span>
                    </div>
                    <div className="ml-auto text-caos-mute">
                      Δ {it.deviation_pct > 0 ? "+" : ""}{Math.round(it.deviation_pct * 100)}%
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
