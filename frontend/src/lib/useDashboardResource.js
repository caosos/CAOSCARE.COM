import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

// Polls one read-only dashboard endpoint. A failed refresh keeps the last
// good data and says so; it never replaces it with an empty view.
export default function useDashboardResource(path, intervalMs = 5000) {
  const [state, setState] = useState({ data: null, error: null, stale: false });
  const alive = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    try {
      const { data } = await api.get(path);
      if (alive.current) setState({ data, error: null, stale: false });
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || "read failed";
      if (alive.current) setState((prev) => ({ data: prev.data, error: message, stale: !!prev.data }));
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    setState({ data: null, error: null, stale: false });
    load();
    const timer = setInterval(load, intervalMs);
    return () => { alive.current = false; clearInterval(timer); };
  }, [load, intervalMs]);

  return { ...state, reload: load };
}
