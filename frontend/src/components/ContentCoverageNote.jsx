import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

// Says why a menu or activity schedule looks empty: nothing is published for
// today, and the last published day. From GET /menu/coverage or
// /schedule/coverage (the same "what residents and Aria see" rules as the
// public reads). Silent while loading or if the check fails; the screen below
// still works.
const WORDS = { menu: { thing: "menu", next: "Paste or email the next menu, then publish it." },
                schedule: { thing: "activities", next: "Paste or email the next activities calendar, then publish it." } };

export function coverageMessage(kind, c) {
  if (!c) return null;
  const w = WORDS[kind];
  if (!c.covers_today) {
    const last = c.last_date ? `The last published day is ${c.last_date}${c.days_ago ? ` (${c.days_ago} day${c.days_ago === 1 ? "" : "s"} ago)` : ""}.` : "Nothing has been published yet.";
    return { tone: "warn", text: `Residents and Aria have no ${w.thing} for today. ${last} ${w.next}` };
  }
  if (c.days_ahead <= 2) return { tone: "info", text: `Published through ${c.last_date} only. ${w.next}` };
  return null;
}

export default function ContentCoverageNote({ kind, refreshKey = 0 }) {
  const [c, setC] = useState(null);
  useEffect(() => {
    let live = true;
    api.get(`/${kind}/coverage`).then(({ data }) => { if (live) setC(data); }).catch(() => {});
    return () => { live = false; };
  }, [kind, refreshKey]);
  const m = coverageMessage(kind, c);
  if (!m) return null;
  return (
    <div className={`rounded-lg px-3 py-2 text-sm mb-4 ${m.tone === "warn" ? "bg-amber-50 text-amber-900" : "bg-caos-ambient text-caos-ink"}`} data-testid={`${kind}-coverage-note`}>
      {m.text}
    </div>
  );
}
