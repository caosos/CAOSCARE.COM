import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function AuthCallback() {
  const nav = useNavigate();
  const loc = useLocation();
  const { fetchMe } = useAuth();
  const processed = useRef(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = loc.hash || window.location.hash;
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) {
      nav("/login");
      return;
    }
    const session_id = m[1];

    (async () => {
      try {
        await api.post("/auth/google/session", { session_id });
        const user = await fetchMe();
        // clear hash
        window.history.replaceState({}, document.title, window.location.pathname);
        nav(user?.role === "admin" ? "/admin" : "/staff", { state: { user } });
      } catch (e) {
        setErr("Authentication failed. Please try again.");
        setTimeout(() => nav("/login"), 1500);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen flex items-center justify-center bg-caos-bone">
      <div className="text-center">
        <div className="w-16 h-16 rounded-full bg-caos-forest caos-orb mx-auto" />
        <p className="mt-6 font-display text-xl text-caos-forest">
          {err || "Signing you in..."}
        </p>
      </div>
    </div>
  );
}
