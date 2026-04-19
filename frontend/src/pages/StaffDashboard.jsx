import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import {
  AlertCircle,
  CheckCircle2,
  MapPin,
  LogOut,
  Shield,
  Activity,
  RefreshCw,
  Users,
  ChevronRight,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import AlertDetailDialog from "./AlertDetailDialog";

function severityColor(s) {
  if (s === "emergency") return { border: "#B6463A", bg: "#FDECE9", text: "#98392F" };
  if (s === "assist") return { border: "#D28D38", bg: "#FDF3E3", text: "#8B5A20" };
  return { border: "#4A7C59", bg: "#EAF3EC", text: "#2F5940" };
}

function timeAgo(iso) {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function StaffDashboard() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [alerts, setAlerts] = useState([]);
  const [locations, setLocations] = useState([]);
  const [stats, setStats] = useState({ active: 0, acknowledged: 0, resolved_24h: 0, emergency_active: 0 });
  const [loading, setLoading] = useState(true);
  const [detailId, setDetailId] = useState(null);

  const fetchAll = async () => {
    try {
      const [aRes, lRes, sRes] = await Promise.all([
        api.get("/alerts/feed"),
        api.get("/locations/latest"),
        api.get("/alerts/stats"),
      ]);
      setAlerts(aRes.data);
      setLocations(lRes.data);
      setStats(sRes.data);
    } catch (e) {
      // stay silent on poll errors
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 3000);
    return () => clearInterval(t);
  }, []);

  const acknowledge = async (id) => {
    try {
      await api.post(`/alerts/${id}/acknowledge`);
      toast.success("Acknowledged");
      fetchAll();
    } catch {
      toast.error("Could not acknowledge");
    }
  };
  const resolve = async (id) => {
    try {
      await api.post(`/alerts/${id}/resolve`);
      toast.success("Resolved");
      fetchAll();
    } catch {
      toast.error("Could not resolve");
    }
  };

  const generateMockLocations = async () => {
    try {
      const { data } = await api.post("/locations/mock/generate");
      toast.success(`Simulated ${data.generated} location pings`);
      fetchAll();
    } catch {
      toast.error("Failed");
    }
  };

  return (
    <div className="min-h-screen bg-caos-bone">
      {/* Top bar */}
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6">
            <Link to="/" data-testid="staff-home-link" className="text-xl">
              <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
              <span className="font-display font-light text-caos-forest">Care</span>
            </Link>
            <span className="text-caos-mute text-sm">· Staff Dashboard</span>
          </div>
          <div className="flex items-center gap-3">
            {user?.role === "admin" && (
              <Link to="/admin" data-testid="nav-admin">
                <Button variant="outline" className="border-2 h-10 rounded-full">
                  <Shield className="w-4 h-4 mr-2" /> Admin
                </Button>
              </Link>
            )}
            <span className="text-sm text-caos-mute hidden md:block" data-testid="staff-user-name">
              {user?.name}
            </span>
            <Button
              variant="outline"
              onClick={async () => {
                await logout();
                nav("/login");
              }}
              data-testid="staff-logout-btn"
              className="border-2 h-10 rounded-full"
            >
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Active" value={stats.active} icon={AlertCircle} tone="emergency" testid="stat-active" />
          <StatCard label="Emergency now" value={stats.emergency_active} icon={AlertCircle} tone="emergency" testid="stat-emergency" />
          <StatCard label="Acknowledged" value={stats.acknowledged} icon={Activity} tone="amber" testid="stat-ack" />
          <StatCard label="Resolved 24h" value={stats.resolved_24h} icon={CheckCircle2} tone="moss" testid="stat-resolved" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Alerts */}
          <section className="lg:col-span-3">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-2xl font-medium text-caos-forest">Live alerts</h2>
              <Button variant="ghost" onClick={fetchAll} data-testid="refresh-alerts-btn">
                <RefreshCw className="w-4 h-4 mr-2" /> Refresh
              </Button>
            </div>

            <div className="space-y-3" data-testid="alerts-list">
              {!loading && alerts.length === 0 && (
                <Card className="p-10 text-center border-caos-line">
                  <CheckCircle2 className="w-10 h-10 text-caos-moss mx-auto" />
                  <p className="mt-3 font-display text-lg text-caos-forest">All clear. No active alerts.</p>
                </Card>
              )}
              {alerts.map((a) => {
                const c = severityColor(a.severity);
                const escLevel = a.escalation_level || 0;
                return (
                  <Card
                    key={a.alert_id}
                    data-testid={`alert-card-${a.alert_id}`}
                    className={`p-5 border-2 relative cursor-pointer hover:shadow-md transition-shadow ${a.severity === "emergency" && a.status === "active" ? "caos-alert-emergency" : ""}`}
                    style={{ borderLeftColor: c.border, borderLeftWidth: 6, background: "#fff" }}
                    onClick={() => setDetailId(a.alert_id)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge
                            data-testid={`alert-sev-${a.alert_id}`}
                            style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
                            className="uppercase tracking-wider font-bold"
                          >
                            {a.severity}
                          </Badge>
                          <Badge variant="outline" className="uppercase tracking-wider text-xs">
                            {a.status}
                          </Badge>
                          {escLevel > 0 && (
                            <Badge
                              data-testid={`esc-${a.alert_id}`}
                              className={`text-white uppercase tracking-wider text-xs font-bold flex items-center gap-1 ${
                                escLevel === 1
                                  ? "bg-caos-amber"
                                  : escLevel === 2
                                  ? "bg-[#c8662b]"
                                  : "bg-caos-terracotta"
                              }`}
                            >
                              <TrendingUp className="w-3 h-3" /> Escalated Lv{escLevel}
                            </Badge>
                          )}
                          <span className="text-caos-mute text-sm">{timeAgo(a.created_at)}</span>
                        </div>
                        <h3 className="font-display text-xl font-medium text-caos-forest mt-2">
                          {a.resident_name || "Unknown resident"}
                        </h3>
                        <p className="text-caos-mute text-sm mt-1">
                          Room {a.room || "?"} · {a.zone || "Location unknown"} · via {a.triggered_by.replace("_", " ")}
                        </p>
                        {a.message && (
                          <p className="text-caos-ink/70 mt-2 italic">"{a.message}"</p>
                        )}
                        {a.acknowledged_by && (
                          <p className="text-caos-mute text-xs mt-2">Acknowledged by {a.acknowledged_by}</p>
                        )}
                      </div>
                      <div className="flex flex-col gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                        {a.status === "active" && (
                          <Button
                            onClick={() => acknowledge(a.alert_id)}
                            data-testid={`ack-btn-${a.alert_id}`}
                            className="bg-caos-amber hover:bg-caos-amber/90 text-white"
                          >
                            Acknowledge
                          </Button>
                        )}
                        <Button
                          onClick={() => setDetailId(a.alert_id)}
                          data-testid={`detail-btn-${a.alert_id}`}
                          variant="outline"
                          className="border-2"
                        >
                          Details <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </section>

          {/* Locations */}
          <section className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-2xl font-medium text-caos-forest">Live locations</h2>
              <Button
                variant="ghost"
                onClick={generateMockLocations}
                data-testid="mock-location-btn"
                title="Simulate mesh network pings"
              >
                <Users className="w-4 h-4 mr-2" /> Simulate
              </Button>
            </div>

            <Card className="border-caos-line bg-white overflow-hidden">
              <div className="divide-y divide-caos-line" data-testid="location-list">
                {locations.map((l) => (
                  <div
                    key={l.resident_id}
                    data-testid={`loc-row-${l.resident_id}`}
                    className="p-4 flex items-center justify-between hover:bg-caos-ambient/50 transition-colors"
                  >
                    <div>
                      <p className="font-semibold text-caos-forest">{l.resident_name}</p>
                      <p className="text-caos-mute text-sm">Room {l.room}</p>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-2 justify-end">
                        <MapPin className="w-4 h-4 text-caos-forest" />
                        <span className="font-semibold text-caos-forest">
                          {l.zone || "Not seen yet"}
                        </span>
                      </div>
                      <p className="text-xs text-caos-mute">
                        {l.last_seen ? timeAgo(l.last_seen) : "—"}
                      </p>
                    </div>
                  </div>
                ))}
                {locations.length === 0 && (
                  <div className="p-6 text-center text-caos-mute">No residents yet.</div>
                )}
              </div>
            </Card>
          </section>
        </div>
      </div>

      <AlertDetailDialog
        alertId={detailId}
        open={!!detailId}
        onOpenChange={(o) => { if (!o) setDetailId(null); }}
        onChanged={fetchAll}
      />
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tone, testid }) {
  const toneMap = {
    emergency: { bg: "#FDECE9", text: "#B6463A" },
    amber: { bg: "#FDF3E3", text: "#D28D38" },
    moss: { bg: "#EAF3EC", text: "#4A7C59" },
    forest: { bg: "#E4EBE7", text: "#153428" },
  };
  const t = toneMap[tone] || toneMap.forest;
  return (
    <Card className="p-5 border-caos-line bg-white" data-testid={testid}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">{label}</p>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: t.bg }}>
          <Icon className="w-4 h-4" style={{ color: t.text }} />
        </div>
      </div>
      <p className="font-display text-4xl font-semibold tracking-tight text-caos-forest mt-2">{value}</p>
    </Card>
  );
}
