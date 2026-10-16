import { useState } from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import RecordsDialog from "../workspace/RecordsDialog";
import { departmentTab } from "../../lib/opsOverview";

// Department status on the Operations overview (#153 slice 2). "Open" and
// "Done today" are exact live counts from the same query as their records
// (GET /ops/metrics/records), so each is a button that opens exactly those
// rows. Columns still counted from the overview's loaded list carry the
// backend's UNVERIFIED reason when it has one.
const EXACT = { open: { metric: "open", label: "open", subtitle: "Open" },
                completed_today: { metric: "done", label: "done today", subtitle: "Done today" } };

function Cell({ n, label, warn, unverified, onOpen, testid }) {
  const body = (
    <>
      <div className={`text-2xl font-display ${warn ? "text-caos-terracotta" : "text-caos-forest"}`}>{n}</div>
      <div className="text-[10px] uppercase tracking-wider text-caos-mute">{label}</div>
      {unverified && <div className="text-[9px] font-bold uppercase text-caos-terracotta" title={unverified}>Unverified</div>}
    </>
  );
  if (!onOpen) return <div className="rounded-xl border border-caos-line p-2" title={unverified || undefined}>{body}</div>;
  return (
    <button type="button" onClick={onOpen} data-testid={testid}
            aria-label={`${n} ${label} — show the records`}
            className="rounded-xl border border-caos-line p-2 hover:border-caos-forest focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1D72D8]">
      {body}
    </button>
  );
}

export default function OverviewDepartments({ departments, scope, onNavigate }) {
  const [openBox, setOpenBox] = useState(null);   // {widget, expected}
  const unverified = (col) => (scope?.unverified_columns || []).includes(col) ? scope.unverified_reason : null;
  const view = { world: "live", date: scope?.date || null, simDay: null };
  const exactCell = (d, col) => {
    const spec = EXACT[col];
    const clickable = scope && !d.is_general && (scope.exact_columns || []).includes(col);
    return (
      <Cell n={d[col]} label={spec.label} testid={`ops-metric-${d.slug}-${col}`}
            unverified={scope && !(scope.exact_columns || []).includes(col) ? "UNVERIFIED: counted from the loaded list" : null}
            onOpen={clickable ? () => setOpenBox({
              expected: d[col],
              widget: { id: `${d.slug}_${col}`, title: d.label, subtitle: spec.subtitle,
                        source: { kind: "metric", metric: spec.metric, department: d.slug } },
            }) : undefined} />
    );
  };
  return (
    <>
      {scope?.explanation && <p className="mb-2 text-xs text-caos-mute" data-testid="ops-dept-scope">{scope.explanation}</p>}
      {scope?.unverified_reason && (
        <p className="mb-3 text-xs font-semibold text-caos-terracotta" data-testid="ops-dept-unverified">
          Overdue, no owner and in progress: {scope.unverified_reason}
        </p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="ops-departments">
        {departments.map((d) => (
          <Card key={d.slug} className="p-4 border-caos-line" data-testid={`ops-dept-${d.slug}`}>
            <div className="flex items-center justify-between">
              <button type="button" className="font-semibold text-caos-forest hover:underline text-left" title="Open this department's work"
                onClick={() => onNavigate?.(departmentTab(d.slug))} data-testid={`ops-dept-open-${d.slug}`}>{d.label} →</button>
              {!d.active && <Badge variant="outline" className="text-[10px] text-caos-mute">inactive</Badge>}
            </div>
            <div className="grid grid-cols-3 gap-2 mt-3 text-center">
              {exactCell(d, "open")}
              <Cell n={d.overdue} label="overdue" warn={d.overdue > 0} unverified={unverified("overdue")} />
              <Cell n={d.unassigned} label="no owner" warn={d.unassigned > 0} unverified={unverified("unassigned")} />
              <Cell n={d.in_progress} label="in progress" unverified={unverified("in_progress")} />
              {exactCell(d, "completed_today")}
            </div>
          </Card>
        ))}
      </div>
      <RecordsDialog widget={openBox?.widget} view={view} open={!!openBox} expectedTotal={openBox?.expected}
                     onOpenChange={(o) => !o && setOpenBox(null)} />
    </>
  );
}
