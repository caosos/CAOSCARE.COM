import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "./App.css";
import { AuthProvider, useAuth } from "./lib/auth";
import { Toaster } from "./components/ui/sonner";

import Landing from "./pages/Landing";
import Login from "./pages/Login";
import AdminLogin from "./pages/AdminLogin";
import Kiosk from "./pages/Kiosk";
import StaffDashboard from "./pages/StaffDashboard";
import Admin from "./pages/Admin";
import Blueprint from "./pages/Blueprint";
import InstallKioskWizard from "./pages/InstallKioskWizard";
import HelpHub from "./pages/HelpHub";
import AuthCallback from "./pages/AuthCallback";
import FamilyPortal from "./pages/FamilyPortal";

function Protected({ children, adminOnly = false, ownerOnly = false }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-caos-bone">
        <div className="w-12 h-12 rounded-full bg-caos-forest caos-orb" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (ownerOnly && user.role !== "owner") return <Navigate to="/admin" replace />;
  // "Admin" tier = owner OR admin (clinical admin nurse). Staff are rejected.
  if (adminOnly && !["owner", "admin"].includes(user.role)) return <Navigate to="/staff" replace />;
  return children;
}

function AppRouter() {
  const location = useLocation();
  // Synchronous OAuth callback detection
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/admin-login" element={<AdminLogin />} />
      <Route path="/kiosk/:kioskId" element={<Kiosk />} />
      <Route path="/family/:token" element={<FamilyPortal />} />
      <Route path="/staff" element={<Protected><StaffDashboard /></Protected>} />
      <Route path="/admin" element={<Protected adminOnly><Admin /></Protected>} />
      <Route path="/admin/blueprint" element={<Protected ownerOnly><Blueprint /></Protected>} />
      <Route path="/admin/install" element={<Protected adminOnly><InstallKioskWizard /></Protected>} />
      <Route path="/admin/install/:kioskId" element={<Protected adminOnly><InstallKioskWizard /></Protected>} />
      <Route path="/admin/help" element={<Protected adminOnly><HelpHub /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <AppRouter />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
