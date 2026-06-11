import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * Official Google Identity Services button (direct — no Emergent).
 *
 * Props:
 *   portal  "staff" | "admin"  — which login page this sits on. The backend
 *           rejects non-admin Google accounts when portal="admin".
 *
 * Requires REACT_APP_GOOGLE_CLIENT_ID at build time. Renders nothing (with a
 * console warning) if it's missing, so the password form still works.
 */
const GSI_SRC = "https://accounts.google.com/gsi/client";

export default function GoogleSignIn({ portal = "staff" }) {
  const nav = useNavigate();
  const { setUser } = useAuth();
  const slotRef = useRef(null);
  const [ready, setReady] = useState(false);
  const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID?.trim();

  useEffect(() => {
    if (!clientId) {
      console.warn("REACT_APP_GOOGLE_CLIENT_ID not set — Google sign-in hidden.");
      return;
    }
    const existing = document.querySelector(`script[src="${GSI_SRC}"]`);
    if (existing && window.google?.accounts?.id) {
      setReady(true);
      return;
    }
    const s = existing || document.createElement("script");
    if (!existing) {
      s.src = GSI_SRC;
      s.async = true;
      s.defer = true;
      document.head.appendChild(s);
    }
    s.addEventListener("load", () => setReady(true));
  }, [clientId]);

  useEffect(() => {
    if (!ready || !clientId || !slotRef.current) return;
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: async (resp) => {
        try {
          const { data } = await api.post("/auth/google/verify", {
            credential: resp.credential,
            portal,
          });
          localStorage.setItem("caos_token", data.token);
          setUser(data.user);
          toast.success(`Welcome, ${data.user.name}`);
          nav(["owner", "admin"].includes(data.user.role) ? "/admin" : "/staff");
        } catch (err) {
          toast.error(err?.response?.data?.detail || "Google sign-in failed");
        }
      },
    });
    window.google.accounts.id.renderButton(slotRef.current, {
      theme: "outline",
      size: "large",
      width: 320,
      text: portal === "admin" ? "signin_with" : "continue_with",
    });
  }, [ready, clientId, portal, nav, setUser]);

  if (!clientId) return null;
  return <div ref={slotRef} data-testid={`google-signin-${portal}`} className="flex justify-center" />;
}
