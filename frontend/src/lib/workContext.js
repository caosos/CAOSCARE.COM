import { useEffect, useState } from "react";

const TOKEN_KEY = "caos_work_context_token";
const VIEW_KEY = "caos_work_context_view";
const EVENT = "caos-work-context-change";

export function workContextToken() {
  return sessionStorage.getItem(TOKEN_KEY) || null;
}

export function readWorkContext() {
  try {
    const value = JSON.parse(sessionStorage.getItem(VIEW_KEY) || "null");
    return value?.work_context_id ? value : null;
  } catch {
    return null;
  }
}

export function saveWorkContext(token, context) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(VIEW_KEY, JSON.stringify(context));
  window.dispatchEvent(new Event(EVENT));
}

export function clearWorkContext() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(VIEW_KEY);
  window.dispatchEvent(new Event(EVENT));
}

export function useWorkContext() {
  const [context, setContext] = useState(readWorkContext);
  useEffect(() => {
    const update = () => setContext(readWorkContext());
    window.addEventListener(EVENT, update);
    return () => window.removeEventListener(EVENT, update);
  }, []);
  useEffect(() => {
    if (!context?.expires_at) return undefined;
    const remaining = (context.expires_at * 1000) - Date.now();
    if (remaining <= 0) {
      clearWorkContext();
      return undefined;
    }
    const timer = setTimeout(clearWorkContext, remaining);
    return () => clearTimeout(timer);
  }, [context?.expires_at]);
  return context;
}
