// Delivery truth for outbound notifications, mirroring NotificationStatus in
// backend/models.py. One place decides what each status may claim, so no
// screen can show "sent" for something that was only recorded.
const STATUS = {
  logged: { label: "Recorded only - not sent", tone: "text-caos-mute", delivered: false },
  failed: { label: "Failed", tone: "text-caos-terracotta", delivered: false },
  sent: { label: "Accepted by provider", tone: "text-caos-forest", delivered: false },
  delayed: { label: "Delivery delayed", tone: "text-caos-terracotta", delivered: false },
  bounced: { label: "Bounced", tone: "text-caos-terracotta", delivered: false },
  complained: { label: "Marked as spam", tone: "text-caos-terracotta", delivered: false },
  delivered: { label: "Delivered", tone: "text-caos-moss", delivered: true },
  queued: { label: "Queued (legacy)", tone: "text-caos-mute", delivered: false },
};

export function deliveryStatus(status) {
  return STATUS[status] || { label: status || "Unknown", tone: "text-caos-mute", delivered: false };
}

const ROUTES = {
  department_contact: "Department inbox",
  department_staff: "Department staff",
  admin_fallback: "Admin fallback",
};

export function routeLabel(route) {
  return ROUTES[route] || null;
}

// Inbound email outcomes (routes/email_inbound.py).
const INBOUND = {
  routed: { label: "Routed", tone: "text-caos-moss" },
  quarantined: { label: "Quarantined - sender not approved", tone: "text-caos-terracotta" },
  unrecognized_recipient: { label: "Unknown address", tone: "text-caos-mute" },
  error: { label: "Error", tone: "text-caos-terracotta" },
  received: { label: "Received", tone: "text-caos-mute" },
};

export function inboundStatus(status) {
  return INBOUND[status] || { label: status || "Unknown", tone: "text-caos-mute" };
}

export const INBOUND_LANES = [
  { value: "menu", label: "Menu (kitchen)" },
  { value: "activities", label: "Activities" },
];
