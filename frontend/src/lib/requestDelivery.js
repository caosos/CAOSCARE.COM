// Was the department actually told about a request? (routes/request_delivery.py)
// The backend returns one state + label; this only decides how loudly to show it.
export function deliveryTone(d) {
  if (!d) return null;
  if (d.state === "delivered" || d.state === "sent") return "ok";
  if (d.state === "simulated") return "muted";
  return "warn";                 // not_sent, failed, none: nobody was reached
}
export function showDelivery(d) { return !!d && deliveryTone(d) !== "ok"; }
