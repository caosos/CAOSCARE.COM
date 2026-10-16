// Values for the workspace boxes, and the records behind one box.
// A metric box's value is the `total` of the same records query its
// drill-down uses (page_size=1), so the two always agree.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { WIDGET_BY_ID } from "./workspaceCatalog";

export function periodParams(view) {
  const p = { world: view.world };
  if (view.world === "simulated") {
    if (view.simDay != null) p.sim_day = view.simDay;
  } else if (view.date) {
    p.date = view.date;
  }
  return p;
}

export async function fetchBox(widget, view) {
  const src = widget.source;
  const base = periodParams(view);
  if (src.kind === "metric") {
    const { data } = await api.get("/ops/metrics/records", {
      params: { ...base, metric: src.metric, department: src.department, origin: src.origin, page_size: 1 },
    });
    return { value: data.total, explanation: data.explanation, period: data.period, run: data.run };
  }
  if (src.kind === "widget") {
    const { data } = await api.get(`/ops/metrics/widgets/${src.name}`, { params: base });
    return { value: data.value, explanation: data.explanation, unverified: data.unverified,
             period: data.period, run: data.run };
  }
  return { value: null };
}

export async function fetchRecords(widget, view, { page = 1, q = "", origin } = {}) {
  const src = widget.source;
  const base = periodParams(view);
  if (src.kind === "widget") {
    const { data } = await api.get(`/ops/metrics/widgets/${src.name}`, { params: base });
    return { kind: "list", ...data };
  }
  const { data } = await api.get("/ops/metrics/records", {
    params: { ...base, metric: src.metric, department: src.department, origin: origin ?? src.origin,
              q: q || undefined, page, page_size: 50 },
  });
  return { kind: "tasks", ...data };
}

// Polls every visible box; keeps the last good value when a refresh fails
// and marks the box as failed rather than showing a false zero.
export function useBoxValues(ids, view, intervalMs = 10000) {
  const [values, setValues] = useState({});
  const key = `${ids.join(",")}|${view.world}|${view.date}|${view.simDay}`;
  const alive = useRef(true);
  const current = useRef(key);
  current.current = key;
  const load = useCallback(async () => {
    const mine = key;
    // Each box shows its own answer as soon as it arrives; a slow box never
    // holds back the others.
    await Promise.all(ids.map(async (id) => {
      const widget = WIDGET_BY_ID[id];
      let v;
      if (!widget || widget.source.kind === "panel") v = { value: null };
      else {
        try { v = { ...(await fetchBox(widget, view)), error: null }; }
        catch (e) { v = { error: e?.response?.data?.detail || "Could not load" }; }
      }
      if (!alive.current || current.current !== mine) return;   // a newer view replaced this one
      setValues((prev) => ({ ...prev, [id]: v.error ? { ...prev[id], error: v.error } : v }));
    }));
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  // A different world/period: clear, so the previous view's numbers are
  // never shown under the new label while the new ones load.
  useEffect(() => { setValues({}); }, [key]);
  useEffect(() => {
    alive.current = true;
    load();
    const t = setInterval(load, intervalMs);
    return () => { alive.current = false; clearInterval(t); };
  }, [load, intervalMs]);
  return { values, reload: load };
}
