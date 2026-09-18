import { useState, useEffect } from "react";

// Shared "should this surface render its compact (card/stacked) presentation
// instead of its desktop table" breakpoint - one source of truth so every
// data-heavy admin/staff surface switches at the same width instead of each
// component guessing its own. 1024px (Tailwind's `lg`) puts a portrait
// tablet (768px) in the compact presentation and a landscape tablet/laptop
// (1024px+) in the table - matches Tailwind's own `lg:` utility classes
// used alongside this hook, so the two can't silently disagree.
const COMPACT_BREAKPOINT = "(max-width: 1023px)";

export function useIsCompact() {
  const [isCompact, setIsCompact] = useState(
    () => typeof window !== "undefined" && window.matchMedia(COMPACT_BREAKPOINT).matches
  );

  useEffect(() => {
    const mql = window.matchMedia(COMPACT_BREAKPOINT);
    const onChange = (e) => setIsCompact(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return isCompact;
}
