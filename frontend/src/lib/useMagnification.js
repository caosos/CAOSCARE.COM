import { useEffect, useState } from "react";
import { getMagnification, setMagnification, clampMagnification, MAGNIFICATION_EVENT } from "./realtimeDisplayTools";

/**
 * Applies the resident's persisted display scale to the whole document
 * (see realtimeDisplayTools.js for why root-font-size, not a CSS class) and
 * keeps React state in sync whenever it changes - from THIS hook's own
 * setter (an on-screen +/- tap) or from Aria's set_magnification tool
 * running in the same tab (a CustomEvent, since the tool dispatch code has
 * no React context of its own to update).
 */
export function useMagnification() {
  const [scale, setScale] = useState(() => getMagnification());

  useEffect(() => {
    document.documentElement.style.fontSize = `${scale}%`;
  }, [scale]);

  useEffect(() => {
    const onChange = (e) => setScale(clampMagnification(e.detail));
    window.addEventListener(MAGNIFICATION_EVENT, onChange);
    return () => window.removeEventListener(MAGNIFICATION_EVENT, onChange);
  }, []);

  return { scale, setScale: (pct) => setScale(setMagnification(pct)) };
}
