// Kiosk inventory counts that never invent health. RQ-035 removes `status` for non-admin callers, so a missing
// status means UNKNOWN, not online. `loaded` false = the request failed (unavailable), distinct from an empty list.
export function kioskSummary(kiosks, loaded = true) {
  if (loaded === null) return { total: 0, known: 0, online: 0, offline: 0, unknown: 0, unavailable: false, loading: true };
  if (!loaded || !Array.isArray(kiosks)) return { total: 0, known: 0, online: 0, offline: 0, unknown: 0, unavailable: true };
  let online = 0, offline = 0, unknown = 0;
  for (const k of kiosks) {
    if (k && k.status === "online") online += 1;
    else if (k && k.status === "offline") offline += 1;
    else unknown += 1;
  }
  return { total: kiosks.length, known: online + offline, online, offline, unknown, unavailable: false };
}

// What the tile shows. `healthy` only when every kiosk's status is known and online.
export function kioskTile(sum, restricted = false) {
  if (sum.loading) return { value: "…", detail: "loading", healthy: false, note: null };
  if (sum.unavailable) return { value: "—", detail: "status unavailable", healthy: false, note: "Could not load kiosks" };
  if (sum.total === 0) return { value: "0", detail: "/ 0 kiosks", healthy: false, note: null };
  if (sum.known === 0) return { value: "—", detail: `/ ${sum.total} kiosks, ${restricted ? "status not available to your role" : "status unknown"}`, healthy: false, note: null };
  const note = sum.unknown > 0 ? `${sum.unknown} status unknown` : sum.offline > 0 ? `${sum.offline} offline` : null;
  return { value: String(sum.online), detail: `/ ${sum.total} in service`, healthy: sum.unknown === 0 && sum.offline === 0, note };
}

// Generic tile for any inventory whose request failed or is still loading: never a false 0 / 0.
// ok: null = loading, false = request failed, true = loaded.
export function availabilityTile(ok) {
  if (ok === null) return { value: "…", detail: "loading", healthy: false, note: null };
  if (ok === false) return { value: "—", detail: "unavailable", healthy: false, note: "Could not load" };
  return null;
}
