// The signed-in user's box arrangement, loaded from and saved to the server
// (/me/dashboard-layout). Saves are debounced; a 409 (saved from another
// tab) reloads the server copy instead of overwriting it.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { defaultLayout, normalizeLayout } from "./workspaceCatalog";

const WORKSPACE = "live_ops";

export function moveBox(boxes, fromId, toId) {
  const order = [...boxes].sort((a, b) => a.x - b.x);
  const from = order.findIndex((b) => b.id === fromId);
  const to = order.findIndex((b) => b.id === toId);
  if (from < 0 || to < 0 || from === to) return boxes;
  const [item] = order.splice(from, 1);
  order.splice(to, 0, item);
  return order.map((b, i) => ({ ...b, x: i }));
}

export function stepBox(boxes, id, delta) {
  const visible = [...boxes].sort((a, b) => a.x - b.x).filter((b) => !b.hidden);
  const i = visible.findIndex((b) => b.id === id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= visible.length) return boxes;
  return moveBox(boxes, id, visible[j].id);
}

export function useWorkspaceLayout() {
  const [boxes, setBoxes] = useState(null);
  const [status, setStatus] = useState("loading");   // loading | saved | saving | error | conflict
  const version = useRef(0);
  const timer = useRef(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/me/dashboard-layout", { params: { workspace: WORKSPACE } });
      const saved = data.layout;
      version.current = saved?.version || 0;
      setBoxes(saved ? normalizeLayout(saved.boxes) : defaultLayout());
      setStatus("saved");
    } catch {
      setBoxes((b) => b || defaultLayout());
      setStatus("error");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = useCallback((next) => {
    clearTimeout(timer.current);
    setStatus("saving");
    timer.current = setTimeout(async () => {
      try {
        const { data } = await api.put("/me/dashboard-layout",
          { workspace: WORKSPACE, version: version.current, boxes: next });
        version.current = data.layout.version;
        setStatus("saved");
      } catch (e) {
        if (e?.response?.status === 409) {
          setStatus("conflict");
          load();
        } else {
          setStatus("error");
        }
      }
    }, 600);
  }, [load]);

  const update = useCallback((fn) => {
    setBoxes((prev) => {
      const next = fn(prev);
      if (next !== prev) save(next);
      return next;
    });
  }, [save]);

  const reset = useCallback(async () => {
    clearTimeout(timer.current);
    await api.delete("/me/dashboard-layout", { params: { workspace: WORKSPACE } });
    version.current = 0;
    setBoxes(defaultLayout());
    setStatus("saved");
  }, []);

  return { boxes, status, update, reset };
}
