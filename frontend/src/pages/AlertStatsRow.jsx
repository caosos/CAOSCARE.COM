import React from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/ui/card";
import { AlertCircle, CheckCircle2, Activity, TrendingUp } from "lucide-react";

// The staff-dashboard stat row, extracted so StaffDashboard.jsx doesn't grow.
// Every card drills into the matching filtered view - Active/Emergency/
// Acknowledged/Resolved -> /alerts?status=..., Pattern flags -> Insights.
const TONES = {
  emergency: { bg: "#FDECE9", text: "#B6463A" },
  amber: { bg: "#FDF3E3", text: "#D28D38" },
  moss: { bg: "#EAF3EC", text: "#4A7C59" },
  forest: { bg: "#E4EBE7", text: "#153428" },
};

function StatCard({ label, value, icon: Icon, tone, testid }) {
  const t = TONES[tone] || TONES.forest;
  return (
    <Card className="p-5 border-caos-line bg-white hover:border-caos-forest transition-colors cursor-pointer" data-testid={testid}>
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

export default function AlertStatsRow({ stats, insightSummary }) {
  const cards = [
    ["Active", stats.active, AlertCircle, "emergency", "active", "/alerts?status=active"],
    ["Emergency now", stats.emergency_active, AlertCircle, "emergency", "emergency", "/alerts?status=active&severity=emergency"],
    ["Acknowledged", stats.acknowledged, Activity, "amber", "ack", "/alerts?status=acknowledged"],
    ["Resolved 24h", stats.resolved_24h, CheckCircle2, "moss", "resolved", "/alerts?status=resolved"],
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
      {cards.map(([label, value, icon, tone, key, to]) => (
        <Link key={key} to={to} className="block" data-testid={`stat-${key}-link`}>
          <StatCard label={label} value={value} icon={icon} tone={tone} testid={`stat-${key}`} />
        </Link>
      ))}
      <Link to="/admin?tab=insights" className="block" data-testid="stat-insights-link">
        <Card className="p-5 border-caos-line bg-white hover:border-caos-forest transition-colors cursor-pointer">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Pattern flags</p>
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#FDF3E3]">
              <TrendingUp className="w-4 h-4 text-caos-amber" />
            </div>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <p className="font-display text-4xl font-semibold tracking-tight text-caos-forest">{insightSummary.total}</p>
            {insightSummary.concern > 0 && (
              <span className="text-xs font-bold text-caos-terracotta uppercase tracking-wider">{insightSummary.concern} concern</span>
            )}
          </div>
        </Card>
      </Link>
    </div>
  );
}
