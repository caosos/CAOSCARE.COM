// Shared by the clinician screen and its recent-events list.
export const CATEGORY_META = {
  bathroom:    { label: "Bathroom",    color: "#4A7C59" },
  fall:        { label: "Fall",        color: "#B6463A" },
  pain:        { label: "Pain",        color: "#D4954A" },
  medication:  { label: "Medication",  color: "#7A6B56" },
  lonely:      { label: "Loneliness",  color: "#8E7AB5" },
  confusion:   { label: "Confusion",   color: "#5C7B8A" },
  meal:        { label: "Meal",        color: "#9B8550" },
  other:       { label: "Other",       color: "#7A6B56" },
  unclassified:{ label: "Unclassified",color: "#A8A29E" },
};

export function fmtSeconds(s) {
  if (s === null || s === undefined) return "—";
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}
