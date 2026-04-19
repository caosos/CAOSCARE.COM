import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";

// Very simple 2-floor schematic. Real installations can replace this with an SVG
// exported from a CAD drawing — every rect just needs data-zone attributes.
const FLOORS = [
  {
    id: "1",
    label: "Floor 1 — East & West wings",
    // [x, y, w, h, zone_label, room_hint]
    rects: [
      [30, 30, 90, 60, "First Floor East", "101-120"],
      [130, 30, 90, 60, "First Floor East", "Dining"],
      [230, 30, 120, 60, "Common Areas", "Lobby"],
      [360, 30, 90, 60, "First Floor West", "Chapel"],
      [460, 30, 120, 60, "First Floor West", "121-140"],
      [30, 100, 150, 60, "Communal Bathroom - East", "Bath E"],
      [190, 100, 200, 60, "Common Areas", "Hallway"],
      [400, 100, 180, 60, "Communal Bathroom - West", "Bath W"],
      [30, 170, 300, 50, "Staff Only — Medication Room", "Med Room"],
      [340, 170, 240, 50, "Outside — Parking Lot", "Parking"],
    ],
  },
  {
    id: "2",
    label: "Floor 2 — Lounge",
    rects: [
      [30, 30, 180, 80, "Second Floor", "201-220"],
      [220, 30, 180, 80, "Second Floor", "Lounge"],
      [410, 30, 170, 80, "Second Floor", "221-240"],
    ],
  },
];

export default function FloorPlanTab() {
  const [locations, setLocations] = useState([]);

  const fetchAll = async () => {
    try { const { data } = await api.get("/locations/latest"); setLocations(data); }
    catch { /* silent */ }
  };
  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 5000);
    return () => clearInterval(t);
  }, []);

  // Group residents by zone
  const byZone = useMemo(() => {
    const m = {};
    for (const l of locations) {
      const z = l.zone || "Unknown";
      if (!m[z]) m[z] = [];
      m[z].push(l);
    }
    return m;
  }, [locations]);

  const colorFor = (idx) => {
    // small accessible palette
    const palette = ["#153428", "#4A7C59", "#B6463A", "#D28D38", "#2F5940", "#8B5A20", "#3C6B4C"];
    return palette[idx % palette.length];
  };

  return (
    <Card className="border-caos-line p-6" data-testid="floorplan-tab-root">
      <div className="mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Live floor plan</h2>
        <p className="text-caos-mute text-sm mt-1">
          Each dot is a resident at their most-recent mesh / pendant ping. Refreshes every 5s.
          Replace these zones with a real CAD export when you pilot the first facility.
        </p>
      </div>

      <div className="space-y-8">
        {FLOORS.map((floor) => (
          <div key={floor.id} data-testid={`floor-${floor.id}`}>
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-caos-mute mb-2">{floor.label}</p>
            <div className="w-full overflow-x-auto">
              <svg viewBox="0 0 610 230" className="w-full max-w-4xl h-[230px] rounded-2xl bg-caos-ambient border border-caos-line">
                {floor.rects.map((rect, i) => {
                  const [x, y, w, h, zone, hint] = rect;
                  const residentsHere = byZone[zone] || [];
                  const isRestricted = zone.toLowerCase().includes("restricted") || zone.toLowerCase().includes("parking") || zone.toLowerCase().includes("medication room");
                  return (
                    <g key={i}>
                      <rect
                        x={x} y={y} width={w} height={h} rx={6}
                        fill={isRestricted ? "#FDECE9" : "#fff"}
                        stroke={isRestricted ? "#B6463A" : "#D9D4C8"}
                        strokeWidth={1.5}
                      />
                      <text x={x + 6} y={y + 14} fontSize={9} fill="#7A6B56" fontFamily="monospace">
                        {hint}
                      </text>
                      {/* Resident dots — spread them inside the rect */}
                      {residentsHere.map((l, j) => {
                        const cx = x + 12 + ((j * 18) % Math.max(w - 24, 18));
                        const cy = y + h - 14 - 18 * Math.floor(j / Math.max(1, Math.floor((w - 24) / 18)));
                        return (
                          <g key={l.resident_id}>
                            <circle cx={cx} cy={cy} r={6} fill={colorFor(j)} stroke="#fff" strokeWidth={1.5}>
                              <title>{l.resident_name} · Room {l.room} · {zone}</title>
                            </circle>
                          </g>
                        );
                      })}
                    </g>
                  );
                })}
              </svg>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6">
        <p className="text-xs font-bold uppercase tracking-[0.25em] text-caos-mute mb-2">Current roster</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
          {locations.map((l) => (
            <div key={l.resident_id} className="flex items-center justify-between bg-white rounded-lg border border-caos-line px-3 py-2" data-testid={`roster-${l.resident_id}`}>
              <span className="font-semibold text-caos-forest">{l.resident_name}</span>
              <span className="text-caos-mute">{l.zone || "—"}</span>
            </div>
          ))}
          {locations.length === 0 && (
            <p className="text-caos-mute italic col-span-2">No location pings yet. Trigger "Simulate" from the Staff dashboard.</p>
          )}
        </div>
      </div>
    </Card>
  );
}
