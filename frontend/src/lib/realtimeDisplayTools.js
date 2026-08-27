/**
 * Resident display/magnification setting - shared by Aria's set_magnification
 * tool (dispatched here) and the on-screen +/- control (useMagnification.js
 * hook). Both read/write the SAME localStorage key and broadcast the SAME
 * event, so a voice change and a screen tap can never drift into two
 * different "truths" about how big the resident's screen currently is.
 *
 * Applied at the document root (see useMagnification.js) rather than a
 * hand-picked set of CSS selectors - Tailwind's utility classes are
 * rem-based, so scaling the root font-size genuinely reflows the whole
 * resident screen (spacing, buttons, cards, text together), not just a
 * couple of elements someone remembered to special-case.
 */
export const MAGNIFICATION_KEY = "caos_kiosk_magnification";
export const MAGNIFICATION_EVENT = "caos:magnification";
export const MIN_MAGNIFICATION = 50;
export const MAX_MAGNIFICATION = 200;
const STEP = 20;

export function clampMagnification(pct) {
  const n = Number(pct);
  if (!Number.isFinite(n)) return 100;
  return Math.max(MIN_MAGNIFICATION, Math.min(MAX_MAGNIFICATION, Math.round(n)));
}

export function getMagnification() {
  try {
    const raw = localStorage.getItem(MAGNIFICATION_KEY);
    return raw ? clampMagnification(raw) : 100;
  } catch {
    return 100;
  }
}

export function setMagnification(pct) {
  const clamped = clampMagnification(pct);
  try { localStorage.setItem(MAGNIFICATION_KEY, String(clamped)); } catch { /* ignore */ }
  window.dispatchEvent(new CustomEvent(MAGNIFICATION_EVENT, { detail: clamped }));
  return clamped;
}

export async function executeDisplayTool({ name, args }) {
  if (name !== "set_magnification") return undefined;
  const current = getMagnification();
  let next;
  if (typeof args.percent === "number") {
    next = args.percent;
  } else if (args.direction === "bigger") {
    next = current + STEP;
  } else if (args.direction === "smaller") {
    next = current - STEP;
  } else if (args.direction === "reset") {
    next = 100;
  } else {
    return { ok: false, message: "I didn't catch how you'd like the display changed." };
  }
  const applied = setMagnification(next);
  const clampedNote = (args.percent && applied !== Math.round(args.percent)) ? ` (kept within the ${MIN_MAGNIFICATION}-${MAX_MAGNIFICATION}% range)` : "";
  return { ok: true, message: `display set to ${applied}% size${clampedNote}.` };
}
