import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { ShieldCheck, ArrowRight } from "lucide-react";

export default function AdminLogin() {
  const nav = useNavigate();
  const { loginAdmin } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: "", password: "" });

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await loginAdmin(form.email, form.password);
      toast.success(`Welcome, ${u.name}`);
      nav("/admin");
    } catch (err) {
      const status = err?.response?.status;
      const msg = err?.response?.data?.detail || "Sign-in failed";
      toast.error(msg);
      // If the server says these are staff credentials, push them toward /login.
      if (status === 403) {
        setTimeout(() => nav("/login"), 1200);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-5 bg-caos-forest">
      {/* Left: brand + context (3/5 on desktop) */}
      <div className="relative md:col-span-3 hidden md:flex flex-col justify-between p-12 text-white overflow-hidden">
        {/* Grain overlay */}
        <div
          className="absolute inset-0 opacity-[0.06] pointer-events-none"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.6'/></svg>\")",
          }}
        />
        <Link to="/" data-testid="admin-back-home" className="relative z-10 text-2xl">
          <span className="font-display font-bold tracking-tighter">CAOS</span>
          <span className="font-display font-light">Care</span>
          <span className="ml-3 px-2 py-0.5 rounded-full bg-caos-terracotta/30 border border-caos-terracotta/50 text-[10px] font-bold uppercase tracking-[0.22em]">
            Administrator
          </span>
        </Link>

        <div className="relative z-10 max-w-xl">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-caos-terracotta/90 mb-4">
            <ShieldCheck className="w-4 h-4" /> Secure administrator portal
          </div>
          <h2 className="font-display text-4xl md:text-5xl font-light tracking-tight leading-tight">
            Every resident. Every device.
            <br />
            <span className="text-caos-terracotta">One accountable key.</span>
          </h2>
          <p className="mt-6 text-white/70 text-base leading-relaxed max-w-lg">
            This portal is for facility administrators only. Sign-ins are rate-limited,
            audited, and isolated from the staff dashboard.
          </p>
          <div className="mt-10 pt-6 border-t border-white/10 max-w-md">
            <p className="text-[10px] font-bold uppercase tracking-[0.32em] text-white/40">
              Create A Resident Experience
            </p>
            <p className="text-xs mt-1 text-white/70">
              through <b className="text-white">Compassionate Adaptive Resident Engagement</b>
            </p>
            <p className="text-xs text-white/70">
              powered by a <b className="text-white">Cognitive Adaptive Operating System</b>
            </p>
          </div>
        </div>

        <div className="relative z-10 text-xs uppercase tracking-[0.22em] text-white/50">
          If you are staff or a nurse, please use{" "}
          <Link
            to="/login"
            data-testid="admin-to-staff-link"
            className="underline text-white hover:text-caos-terracotta"
          >
            the staff sign-in
          </Link>
          .
        </div>
      </div>

      {/* Right: form (2/5 on desktop) */}
      <div className="md:col-span-2 flex items-center justify-center p-8 md:p-12 bg-caos-bone">
        <div className="w-full max-w-sm">
          <h1 className="font-display text-3xl font-medium text-caos-forest">
            Admin sign-in
          </h1>
          <p className="text-caos-mute mt-2 text-sm">
            Restricted access. Non-admin accounts will be redirected.
          </p>

          <form onSubmit={handleLogin} className="space-y-4 mt-8">
            <div>
              <Label htmlFor="admin-email" className="font-semibold">
                Admin email
              </Label>
              <Input
                id="admin-email"
                type="email"
                required
                autoComplete="username"
                data-testid="admin-login-email-input"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="mt-1"
                placeholder="admin@yourfacility.com"
              />
            </div>
            <div>
              <Label htmlFor="admin-password" className="font-semibold">
                Password
              </Label>
              <Input
                id="admin-password"
                type="password"
                required
                autoComplete="current-password"
                data-testid="admin-login-password-input"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="mt-1"
              />
            </div>

            <Button
              type="submit"
              disabled={loading}
              data-testid="admin-login-submit-btn"
              className="w-full bg-caos-forest hover:bg-caos-forest-hover text-white h-11 rounded-full"
            >
              {loading ? "Signing in…" : "Sign in as administrator"}
            </Button>
          </form>

          <div className="mt-6 text-xs text-caos-mute border-t border-caos-line pt-4 space-y-2">
            <p className="flex items-start gap-2">
              <ShieldCheck className="w-3.5 h-3.5 mt-0.5 text-caos-forest flex-shrink-0" />
              <span>
                Admin attempts are throttled: 5 failures within 15 minutes locks the
                account out of this path.
              </span>
            </p>
            <Link
              to="/login"
              data-testid="admin-login-staff-link"
              className="inline-flex items-center gap-1 text-caos-forest hover:text-caos-forest-hover mt-2 font-medium"
            >
              Staff sign-in <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
