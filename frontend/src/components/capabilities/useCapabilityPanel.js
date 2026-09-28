import { useCallback, useEffect, useRef, useState } from "react";

const PREFIX = "#cap-";

// Open/close state for a page's capability panel. The open demo is
// reflected in the URL hash (#cap-<id>) with replaceState, so a demo can be
// linked to without adding history entries or moving the page.
export default function useCapabilityPanel(byId) {
  const [openId, setOpenId] = useState(null);
  // Keep the last-opened capability mounted while the dialog closes, so the
  // dialog can run its close lifecycle and return focus to the opening card.
  const [shownId, setShownId] = useState(null);
  const openerRef = useRef(null);

  useEffect(() => {
    const id = window.location.hash.startsWith(PREFIX) ? window.location.hash.slice(PREFIX.length) : null;
    if (id && byId[id]) { setOpenId(id); setShownId(id); }
  }, [byId]);

  const setHash = (hash) => {
    const { pathname, search } = window.location;
    window.history.replaceState(window.history.state, "", `${pathname}${search}${hash}`);
  };

  const open = useCallback((id) => {
    if (!byId[id]) return;
    openerRef.current = document.activeElement;
    setOpenId(id);
    setShownId(id);
    setHash(`${PREFIX}${id}`);
  }, [byId]);

  const close = useCallback(() => {
    setOpenId(null);
    if (window.location.hash.startsWith(PREFIX)) setHash("");
  }, []);

  // The dialogs have no Radix trigger, so return focus to the opener ourselves.
  const onCloseAutoFocus = useCallback((event) => {
    const el = openerRef.current;
    if (el && el !== document.body && document.contains(el)) {
      event.preventDefault();
      el.focus({ preventScroll: true });
    }
  }, []);

  return { onCloseAutoFocus, isOpen: Boolean(openId), capability: shownId ? byId[shownId] : null, open, close };
}
