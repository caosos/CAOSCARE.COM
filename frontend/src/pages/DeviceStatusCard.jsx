import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Radio, Watch, Monitor, BatteryLow, CheckCircle2, AlertTriangle } from "lucide-react";

const STATUS_STYLE = {
  online: "bg-caos-moss/15 text-caos-forest border-caos-moss",
  active: "bg-caos-moss/15 text-caos-forest border-caos-moss",
  offline: "bg-caos-terracotta/15 text-caos-terracotta-dark border-caos-terracotta",
  low_battery: "bg-caos-amber/15 text-[#8B5A20] border-caos-amber",
  lost: "bg-caos-line text-caos-mute",
  inactive: "bg-caos-line text-caos-mute",
};

function timeAgo(iso) {
  if (!iso) return "never";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

// Devices in service. Pendants now come from the REAL RF fleet
// (GET /rf/fleet/summary - reads db.rf_devices), not the retired /pendants
// scaffold that always showed 0/0. Role-safe: no RSSI / match score / raw
// fingerprint here. Admin/owner drills into the full RF fleet via the
// Pendants tab.
export default function DeviceStatusCard() {
  const { user } = useAuth();
  const isAdmin = ["owner", "admin"].includes(user?.role);
  const [rf, setRf] = useState({ total: 0, in_service: 0, need_attention: 0, devices: [] });
  const [wearables, setWearables] = useState([]);
  const [kiosks, setKiosks] = useState([]);
  const [activity, setActivity] = useState([]);

  const fetchAll = async () => {
    try {
      const [rfRes, wRes, kRes, aRes] = await Promise.all([
        api.get("/rf/fleet/summary").catch(() => ({ data: { total: 0, in_service: 0, need_attention: 0, devices: [] } })),
        api.get("/wearables").catch(() => ({ data: [] })),
        api.get("/kiosks").catch(() => ({ data: [] })),
        api.get("/alerts", { params: { limit: 20 } }).catch(() => ({ data: [] })),
      ]);
      setRf(rfRes.data || { total: 0, in_service: 0, need_attention: 0, devices: [] });
      setWearables(wRes.data || []);
      setKiosks(kRes.data || []);
      const devTriggered = (aRes.data || []).filter((a) =>
        ["pendant", "rf_pendant", "wearable", "kiosk_button"].includes(a.triggered_by)
      );
      setActivity(devTriggered.slice(0, 12));
    } catch { /* silent */ }
  };

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, []);

  const wearablesOnline = wearables.filter((w) => w.status === "active" || w.status === "online").length;
  const wearablesLowBat = wearables.filter((w) => w.status === "low_battery").length;
  const kiosksOnline = kiosks.filter((k) => k.status !== "offline").length;

  return (
    <Card className="border-caos-line bg-white p-5" data-testid="device-status-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-xl font-medium text-caos-forest">Devices in service</h3>
        <button onClick={fetchAll} className="text-xs font-bold uppercase tracking-widest text-caos-mute hover:text-caos-forest" data-testid="device-refresh-btn">
          refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-5" data-testid="device-inventory-strip">
        <InventoryTile
          icon={<Radio className="w-5 h-5" />} label="Pendants"
          online={rf.in_service} total={rf.total}
          warn={rf.need_attention > 0 ? `${rf.need_attention} need attention — see below` : null}
          to={isAdmin ? "/admin?tab=rf" : null} testid="inv-pendants"
        />
        <InventoryTile
          icon={<Watch className="w-5 h-5" />} label="Wearables"
          online={wearablesOnline} total={wearables.length}
          warn={wearablesLowBat > 0 ? `${wearablesLowBat} low battery` : null}
          to={isAdmin ? "/admin?tab=wearables" : null} testid="inv-wearables"
        />
        <InventoryTile
          icon={<Monitor className="w-5 h-5" />} label="Kiosks"
          online={kiosksOnline} total={kiosks.length} warn={null}
          to={isAdmin ? "/admin?tab=kiosks" : null} testid="inv-kiosks"
        />
      </div>

      {rf.devices.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">Pendant status per resident</p>
          <div className="space-y-1 max-h-56 overflow-y-auto pr-1" data-testid="pendant-status-list">
            {[...rf.devices]
              .sort((a, b) => (a.status === "active" ? 1 : 0) - (b.status === "active" ? 1 : 0))
              .map((p) => (
              <div key={p.rf_device_id} data-testid={`pendant-status-${p.rf_device_id}`} className="text-sm bg-caos-ambient/40 rounded-lg px-3 py-2">
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <span className="font-semibold text-caos-forest">{p.resident_name || p.label || <span className="italic text-caos-mute">Unassigned</span>}</span>
                    {p.room && <span className="text-caos-mute text-xs ml-2">Rm {p.room}</span>}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {p.low_battery && <BatteryLow className="w-3 h-3 text-caos-terracotta" />}
                    <span className="text-[10px] text-caos-mute uppercase tracking-wider">seen {timeAgo(p.last_seen_at)}</span>
                    <Badge className={`uppercase tracking-wider text-[10px] font-bold border ${STATUS_STYLE[p.status] || STATUS_STYLE.inactive}`}>
                      {String(p.status).replace("_", " ")}
                    </Badge>
                  </div>
                </div>
                {p.reason && (
                  <div className="text-[11px] text-caos-terracotta mt-1 font-medium" data-testid={`pendant-reason-${p.rf_device_id}`}>
                    {p.reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {wearables.length > 0 && (
        <div className="mb-5">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">Wearable status</p>
          <div className="space-y-1 max-h-40 overflow-y-auto pr-1" data-testid="wearable-status-list">
            {wearables.map((w) => (
              <div key={w.wearable_id} data-testid={`wearable-status-${w.wearable_id}`} className="flex items-center justify-between text-sm bg-caos-ambient/40 rounded-lg px-3 py-2">
                <div className="min-w-0">
                  <span className="font-semibold text-caos-forest">{w.resident_name || <span className="italic text-caos-mute">Unassigned</span>}</span>
                  <span className="text-caos-mute text-xs ml-2">{w.device_type?.replace("_", " ")}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {w.battery_percent != null && (
                    <span className={`text-[10px] uppercase tracking-wider flex items-center gap-1 ${w.battery_percent < 20 ? "text-caos-terracotta-dark" : "text-caos-mute"}`}>
                      {w.battery_percent < 20 && <BatteryLow className="w-3 h-3" />}
                      {w.battery_percent}%
                    </span>
                  )}
                  <Badge className={`uppercase tracking-wider text-[10px] font-bold border ${STATUS_STYLE[w.status] || STATUS_STYLE.inactive}`}>
                    {w.status?.replace("_", " ")}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">Recent device activity</p>
        <div className="space-y-1 max-h-64 overflow-y-auto pr-1" data-testid="device-activity-list">
          {activity.map((a) => {
            const canDrill = isAdmin && a.resident_id;
            const RowTag = canDrill ? Link : "div";
            const rowProps = canDrill ? { to: `/admin?tab=residents&resident=${a.resident_id}` } : {};
            return (
              <RowTag key={a.alert_id} data-testid={`device-activity-${a.alert_id}`} {...rowProps}
                className={`flex items-start justify-between gap-3 text-sm bg-white rounded-lg border border-caos-line px-3 py-2 ${canDrill ? "hover:border-caos-forest cursor-pointer" : ""}`}>
                <div className="shrink-0 mt-0.5">
                  {(a.triggered_by === "pendant" || a.triggered_by === "rf_pendant") && <Radio className="w-4 h-4 text-caos-forest" />}
                  {a.triggered_by === "wearable" && <Watch className="w-4 h-4 text-caos-forest" />}
                  {a.triggered_by === "kiosk_button" && <Monitor className="w-4 h-4 text-caos-forest" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-caos-forest">
                    <span className="font-semibold">{a.resident_name || "Unassigned device"}</span>
                    {a.room && <span className="text-caos-mute"> · Rm {a.room}</span>}
                  </div>
                  <div className="text-xs text-caos-mute">{a.message}</div>
                </div>
                <div className="shrink-0 text-right">
                  <Badge className={`uppercase tracking-wider text-[10px] font-bold ${a.severity === "emergency" ? "bg-caos-terracotta text-white" : a.severity === "assist" ? "bg-caos-amber text-white" : "bg-caos-forest text-white"}`}>
                    {String(a.triggered_by || "").replace("_button", "").replace("_", " ")}
                  </Badge>
                  <div className="text-[10px] text-caos-mute tabular-nums mt-0.5">{timeAgo(a.created_at)} ago</div>
                </div>
              </RowTag>
            );
          })}
          {activity.length === 0 && (
            <p className="text-center text-caos-mute py-4 italic text-sm">No device activity yet.</p>
          )}
        </div>
      </div>
    </Card>
  );
}

function InventoryTile({ icon, label, online, total, warn, to, testid }) {
  const healthy = online === total && total > 0;
  const inner = (
    <div className={`rounded-2xl border-2 p-3 h-full ${healthy ? "border-caos-moss bg-caos-moss/5" : warn ? "border-caos-amber bg-caos-amber/5" : "border-caos-line bg-caos-ambient/40"} ${to ? "hover:border-caos-forest cursor-pointer transition-colors" : ""}`} data-testid={testid}>
      <div className="flex items-center gap-2 text-caos-forest">
        {icon}
        <span className="text-xs font-bold uppercase tracking-widest text-caos-mute">{label}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="font-display text-3xl font-semibold text-caos-forest tabular-nums">{online}</span>
        <span className="text-caos-mute text-sm">/ {total} in service</span>
        {healthy ? <CheckCircle2 className="w-4 h-4 text-caos-moss ml-auto" /> : warn ? <AlertTriangle className="w-4 h-4 text-caos-amber ml-auto" /> : null}
      </div>
      {warn && <p className="text-[11px] text-caos-amber mt-1 font-semibold">{warn}</p>}
    </div>
  );
  return to ? <Link to={to} className="block">{inner}</Link> : inner;
}
