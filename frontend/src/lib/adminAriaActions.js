/**
 * Generic executor for the ordered ui_actions array returned by
 * POST /admin-assistant/chat (2026-08-27, "Aria should visually guide the
 * administrator, not just describe"). Plays actions in sequence - the
 * administrator visibly sees the screen move, not everything changing at
 * once - then resolves once the sequence is done so the caller can show
 * Aria's text reply.
 *
 * Targets are addressed by the SAME data-testid values every Admin tab
 * component already renders per row (res-row-{id}, dev-row-{id}) - no new
 * DOM attributes needed anywhere. Any future Admin component that follows
 * this existing convention is automatically a valid Aria target; nothing
 * bespoke has to be built per page.
 */
const SELECTOR_BY_KIND = {
  resident: (id) => `[data-testid="res-row-${id}"]`,
  device: (id) => `[data-testid="dev-row-${id}"]`,
};

function targetSelector(target) {
  const [kind, id] = target.split(/:(.+)/); // split on first ':' only
  const build = SELECTOR_BY_KIND[kind];
  return build ? build(id) : null;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Broadcast, not prop-drilled - the spotlight overlay is mounted once at
// the Admin root and listens for this, same pattern as the magnification
// feature's cross-module event bus.
export const ARIA_HIGHLIGHT_EVENT = "caos:admin-aria-highlight";

function dispatchHighlight(targets, label) {
  window.dispatchEvent(new CustomEvent(ARIA_HIGHLIGHT_EVENT, { detail: { targets, label } }));
}

export function clearHighlight() {
  dispatchHighlight([], null);
}

/**
 * Runs the ordered actions. `onNavigate` should be the Admin page's own
 * setActiveTab - the same mechanism already used for direct tab clicks, so
 * Aria-driven and human-driven navigation are indistinguishable to the
 * rest of the app.
 */
export async function executeUiActions(actions, { onNavigate } = {}) {
  for (const action of actions || []) {
    if (action.type === "navigate" && action.section) {
      onNavigate?.(action.section);
      await delay(350); // let the tab actually render before we scroll/highlight into it
    } else if (action.type === "scroll_to") {
      const el = (action.targets || []).map(targetSelector).filter(Boolean).map((sel) => document.querySelector(sel)).find(Boolean);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      await delay(450); // let the smooth scroll settle before measuring for a highlight
    } else if (action.type === "highlight") {
      dispatchHighlight(action.targets || [], action.label || null);
      await delay(1600); // hold the spotlight long enough to actually see it before the next step
    }
  }
}
