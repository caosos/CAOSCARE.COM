import React, { useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { ARIA_HIGHLIGHT_EVENT } from "../../lib/adminAriaActions";

const SELECTOR_BY_KIND = {
  resident: (id) => `[data-testid="res-row-${id}"]`,
  device: (id) => `[data-testid="dev-row-${id}"]`,
};

function resolveElements(targets) {
  return (targets || [])
    .map((t) => {
      const [kind, id] = t.split(/:(.+)/);
      const build = SELECTOR_BY_KIND[kind];
      return build ? document.querySelector(build(id)) : null;
    })
    .filter(Boolean);
}

function unionRect(els) {
  if (!els.length) return null;
  const rects = els.map((el) => el.getBoundingClientRect());
  return {
    top: Math.min(...rects.map((r) => r.top)),
    left: Math.min(...rects.map((r) => r.left)),
    right: Math.max(...rects.map((r) => r.right)),
    bottom: Math.max(...rects.map((r) => r.bottom)),
  };
}

/**
 * Restrained, temporary spotlight around whatever Aria is currently
 * showing the administrator - mounted once at the Admin root. Purely
 * visual: scrollIntoView (via adminAriaActions.js) already moved the
 * viewport; this only draws attention, never steals or traps keyboard
 * focus (no .focus() call anywhere here), per the accessibility
 * requirement. Auto-clears on a timer or when the next highlight replaces
 * it - whichever comes first.
 */
export default function AriaSpotlight() {
  const [box, setBox] = useState(null);
  const [label, setLabel] = useState(null);
  const clearTimer = useRef(null);

  useEffect(() => {
    const update = (targets) => {
      const els = resolveElements(targets);
      setBox(unionRect(els));
    };

    const onHighlight = (e) => {
      clearTimeout(clearTimer.current);
      const { targets, label: lbl } = e.detail || {};
      if (!targets || !targets.length) {
        setBox(null);
        setLabel(null);
        return;
      }
      update(targets);
      setLabel(lbl || null);
      clearTimer.current = setTimeout(() => { setBox(null); setLabel(null); }, 3200);

      const onReflow = () => update(targets);
      window.addEventListener("scroll", onReflow, true);
      window.addEventListener("resize", onReflow);
      setTimeout(() => {
        window.removeEventListener("scroll", onReflow, true);
        window.removeEventListener("resize", onReflow);
      }, 2600);
    };

    window.addEventListener(ARIA_HIGHLIGHT_EVENT, onHighlight);
    return () => {
      window.removeEventListener(ARIA_HIGHLIGHT_EVENT, onHighlight);
      clearTimeout(clearTimer.current);
    };
  }, []);

  if (!box) return null;

  return (
    <div
      data-testid="admin-aria-spotlight"
      className="fixed z-50 pointer-events-none rounded-xl transition-all duration-300"
      style={{
        top: box.top - 6, left: box.left - 6, width: box.right - box.left + 12, height: box.bottom - box.top + 12,
        // caos-terracotta is a hand-authored CSS custom property (see
        // index.css), not a Tailwind theme color - ring-*/shadow-* utility
        // classes can't resolve it (confirmed live: they silently fell back
        // to Tailwind's default blue). Composing the ring + page dim as one
        // inline box-shadow is the only way to guarantee the real brand
        // color actually renders here.
        boxShadow: "0 0 0 4px var(--caos-terracotta), 0 0 0 9999px rgba(0,0,0,0.25)",
      }}
    >
      {label && (
        <span
          className="absolute -top-8 left-0 inline-flex items-center gap-1 rounded-full text-white text-xs font-semibold px-3 py-1 shadow-md whitespace-nowrap"
          style={{ background: "var(--caos-terracotta)" }}
        >
          <Sparkles className="w-3 h-3" /> Aria is showing you: {label}
        </span>
      )}
    </div>
  );
}
