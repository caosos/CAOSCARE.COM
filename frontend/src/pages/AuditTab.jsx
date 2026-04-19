import React, { useEffect, useState } from "react";
import { api, API } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Download, FileText, Shield } from "lucide-react";
import { toast } from "sonner";

// YYYY-MM-DD for <input type="date"> defaults
const today = () => new Date().toISOString().slice(0, 10);
const thirtyAgo = () => new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

export default function AuditTab() {
  const [start, setStart] = useState(thirtyAgo());
  const [end, setEnd] = useState(today());
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchSummary = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/audit/summary", {
        params: { start: `${start}T00:00:00+00:00`, end: `${end}T23:59:59+00:00` },
      });
      setSummary(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load summary");
    }
    setLoading(false);
  };

  useEffect(() => { fetchSummary(); /* eslint-disable-next-line */ }, []);

  const download = async (kind) => {
    try {
      const token = localStorage.getItem("caos_token");
      const params = new URLSearchParams({
        start: `${start}T00:00:00+00:00`,
        end: `${end}T23:59:59+00:00`,
      });
      const res = await fetch(`${API}/audit/${kind}.csv?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `caos-${kind}-${start}-to-${end}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(`${kind}.csv downloaded`);
    } catch (err) {
      toast.error(err?.message || "Download failed");
    }
  };

  const Row = ({ kind, label, count }) => (
    <div className="flex items-center justify-between p-4 rounded-2xl border border-caos-line bg-white" data-testid={`audit-row-${kind}`}>
      <div className="flex items-center gap-3">
        <FileText className="w-5 h-5 text-caos-forest" />
        <div>
          <div className="font-semibold text-caos-forest">{label}</div>
          <div className="text-caos-mute text-xs uppercase tracking-wider">
            {count != null ? `${count} rows` : "—"}
          </div>
        </div>
      </div>
      <Button onClick={() => download(kind)} disabled={count === 0} data-testid={`audit-download-${kind}`} className="bg-caos-forest hover:bg-caos-forest-hover rounded-full">
        <Download className="w-4 h-4 mr-2" /> Download CSV
      </Button>
    </div>
  );

  return (
    <Card className="border-caos-line p-6 space-y-6" data-testid="audit-tab-root">
      <div>
        <h2 className="font-display text-xl font-medium text-caos-forest flex items-center gap-2">
          <Shield className="w-5 h-5" /> Compliance audit export
        </h2>
        <p className="text-caos-mute text-sm mt-1">
          Downloadable receipts for HIPAA reviews, administrator walkthroughs, and insurance discussions. Every row is UTC-stamped and includes the full chain of custody (who pressed, who acknowledged, who resolved).
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <Label>Start</Label>
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} data-testid="audit-start" />
        </div>
        <div>
          <Label>End</Label>
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} data-testid="audit-end" />
        </div>
        <Button onClick={fetchSummary} variant="outline" className="border-2 rounded-full" data-testid="audit-refresh">
          {loading ? "Loading…" : "Refresh counts"}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Row kind="alerts" label="Alerts (full lifecycle)" count={summary?.alerts} />
        <Row kind="tasks" label="Staff tasks (who / when / duration / notes)" count={summary?.tasks} />
        <Row kind="pages" label="Facility pager events" count={summary?.pages} />
        <Row kind="medications" label="Medication reminder acknowledgements" count={summary?.medications} />
      </div>

      <div className="bg-caos-ambient/60 border border-caos-line rounded-2xl p-4 text-sm text-caos-mute">
        <p className="font-semibold text-caos-forest mb-1">What's included</p>
        <ul className="list-disc ml-5 space-y-1">
          <li><strong>Alerts</strong>: severity, trigger source, resident, acknowledgement + resolution users and timestamps, outcome and close notes.</li>
          <li><strong>Tasks</strong>: category, shift, assignee, start/complete times, duration, notes, completed-by.</li>
          <li><strong>Pages</strong>: RF cap code, urgency, resident enrichment, message body.</li>
          <li><strong>Medications</strong>: reminder title, scheduled time, resident, dose notes, acknowledgement timestamp.</li>
        </ul>
        <p className="mt-3 text-xs">Conversation content and long-term memories are <strong>intentionally excluded</strong> from these exports to protect resident privacy. Those can be reviewed in Admin → Residents → Memory on a per-resident basis.</p>
      </div>
    </Card>
  );
}
