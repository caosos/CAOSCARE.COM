// Mouse/pen/touch rearranging for the workspace boxes.
// Press anywhere on a box (not on a button, link or field) and move a few
// pixels: the box lifts and follows the pointer, the other boxes shuffle
// live to show where it will land, and releasing saves that order. Releasing
// over a gap keeps the last position shown. Escape cancels.
import { useCallback, useRef, useState } from "react";
import { moveBox } from "./useWorkspaceLayout";

const THRESHOLD = 6;   // px before a press becomes a drag (clicks stay clicks)
const INTERACTIVE = "button, a, input, select, textarea, [role='menuitem'], [data-no-drag]";

export function useBoxDrag(boxes, commit) {
  const [drag, setDrag] = useState(null);   // {id, x, y, w, h, ox, oy}
  const [preview, setPreview] = useState(null);   // live order while dragging
  const previewRef = useRef(null);

  const onPointerDown = useCallback((id) => (e) => {
    if (e.button !== 0 || (e.target.closest(INTERACTIVE) && !e.target.closest("[data-drag-handle]"))) return;
    const card = e.currentTarget.getBoundingClientRect();
    const start = { x: e.clientX, y: e.clientY };
    let started = false;
    previewRef.current = boxes;

    const move = (ev) => {
      if (!started) {
        if (Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < THRESHOLD) return;
        started = true;
        document.body.style.userSelect = "none";
      }
      setDrag({ id, x: ev.clientX, y: ev.clientY, w: card.width, h: card.height,
                ox: start.x - card.left, oy: start.y - card.top });
      const over = document.elementFromPoint(ev.clientX, ev.clientY)?.closest("[data-box-id]")?.dataset.boxId;
      if (over && over !== id) {
        previewRef.current = moveBox(previewRef.current, id, over);
        setPreview(previewRef.current);
      }
    };
    const stop = (save) => () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("keydown", key);
      document.body.style.userSelect = "";
      if (started && save && previewRef.current !== boxes) commit(previewRef.current);
      setDrag(null);
      setPreview(null);
    };
    const up = stop(true);
    const key = (ev) => { if (ev.key === "Escape") stop(false)(); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("keydown", key);
  }, [boxes, commit]);

  return { drag, shown: preview || boxes, onPointerDown };
}
