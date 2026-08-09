import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [localBypassActive, setLocalBypassActive] = useState(false);

  useEffect(() => {
    // Cheap, unauthenticated, safe on every path - just tells the UI whether
    // to show a LOCAL OWNER MODE indicator (Terminal 7).
    api
      .get("/auth/local-bypass-status")
      .then(({ data }) => setLocalBypassActive(!!data.active))
      .catch(() => setLocalBypassActive(false));
  }, []);

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      return data;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    // Skip /me check if returning from OAuth callback (AuthCallback will exchange first)
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    // Skip /me probe on public routes (kiosk, family portal, landing) to avoid 401 noise
    const path = window.location.pathname;
    const isPublic = path === "/" || path.startsWith("/kiosk") || path.startsWith("/family/");
    if (isPublic && !localStorage.getItem("caos_token")) {
      setLoading(false);
      return;
    }
    (async () => {
      await fetchMe();
      setLoading(false);
    })();
  }, [fetchMe]);

  const loginJwt = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("caos_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const loginAdmin = async (email, password) => {
    const { data } = await api.post("/auth/admin-login", { email, password });
    localStorage.setItem("caos_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const registerJwt = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    localStorage.setItem("caos_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    localStorage.removeItem("caos_token");
    try {
      await api.post("/auth/logout");
    } catch {}
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser,
        loading,
        fetchMe,
        loginJwt,
        loginAdmin,
        registerJwt,
        logout,
        localBypassActive,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
