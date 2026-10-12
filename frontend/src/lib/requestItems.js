// Supplies/linens asked for on a request ([{item, quantity}], backend StaffTask.items).
export function itemsLine(items) {
  const list = (items || []).filter((i) => i && i.item);
  if (!list.length) return null;
  return `Items: ${list.map((i) => `${i.quantity || 1} × ${i.item}`).join(", ")}`;
}

// Only well-formed items are sent: a name and a whole quantity 1-20.
export function cleanItems(items) {
  if (!Array.isArray(items)) return undefined;
  const out = items
    .filter((i) => i && typeof i.item === "string" && i.item.trim())
    .map((i) => ({ item: i.item.trim().slice(0, 60), quantity: Math.min(20, Math.max(1, parseInt(i.quantity, 10) || 1)) }))
    .slice(0, 10);
  return out.length ? out : undefined;
}
