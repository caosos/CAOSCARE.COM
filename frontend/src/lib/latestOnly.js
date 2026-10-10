// Only the newest request may update the screen: an older, slower reply must not overwrite it.
export function latestOnly() {
  let n = 0;
  return { next: () => ++n, isCurrent: (id) => id === n, invalidate: () => { n += 1; } };
}
