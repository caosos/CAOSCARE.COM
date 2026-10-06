import React from "react";

const TONE = {
  ok: "bg-emerald-100 text-emerald-800",
  warn: "bg-amber-100 text-amber-800",
  bad: "bg-red-100 text-red-800",
  mute: "bg-stone-200 text-stone-700",
  sim: "bg-sky-100 text-sky-800",
};

export default function StatusBadge({ label, tone = "mute", testId }) {
  return (
    <span data-testid={testId}
          className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider ${TONE[tone] || TONE.mute}`}>
      {label}
    </span>
  );
}
