// Fast resident / room finder. Pure - the component just renders what this
// returns. Reuses the resident list the page already has; no new endpoint,
// no second profile store.
//
// A query matches on room number, first name, last name, preferred name, or
// a "first last" phrase. "214", "Helen", "Torres", "Helen Torres" all find
// Helen Torres / Room 214. Results are ranked: exact room, then room
// prefix, then name-start, then name-substring.

function norm(s) {
  return String(s || "").trim().toLowerCase();
}

export function residentTokens(r) {
  const name = norm(r.name);
  const parts = name.split(/\s+/).filter(Boolean);
  return {
    room: norm(r.room),
    first: parts[0] || "",
    last: parts.length > 1 ? parts[parts.length - 1] : "",
    preferred: norm(r.preferred_name),
    full: name,
  };
}

// Returns a score (higher = better) or 0 for no match.
export function scoreResident(r, q) {
  const query = norm(q);
  if (!query) return 0;
  const t = residentTokens(r);
  const isNum = /^\d+$/.test(query);

  if (isNum) {
    if (t.room === query) return 100;
    if (t.room.startsWith(query)) return 70;
    if (t.room.includes(query)) return 40;
    return 0;
  }

  let best = 0;
  const consider = (val, exact, start, sub) => {
    if (!val) return;
    if (val === query) best = Math.max(best, exact);
    else if (val.startsWith(query)) best = Math.max(best, start);
    else if (val.includes(query)) best = Math.max(best, sub);
  };
  consider(t.first, 90, 80, 55);
  consider(t.last, 88, 78, 52);
  consider(t.preferred, 86, 76, 50);
  consider(t.full, 95, 65, 45);
  // "first last" style phrase
  if (query.includes(" ")) {
    const [a, b] = query.split(/\s+/);
    if (a && b && t.first.startsWith(a) && t.last.startsWith(b)) best = Math.max(best, 96);
  }
  return best;
}

export function matchResidents(residents, q, limit = 8) {
  const query = norm(q);
  if (!query) return [];
  return (residents || [])
    .map((r) => ({ r, s: scoreResident(r, query) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s || norm(a.r.name).localeCompare(norm(b.r.name)))
    .slice(0, limit)
    .map((x) => x.r);
}
