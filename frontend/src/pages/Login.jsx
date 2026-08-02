import React, { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import GoogleSignIn from "../components/GoogleSignIn";
import { toast } from "sonner";

const AUTH_IMG =
  "https://images.pexels.com/photos/6203473/pexels-photo-6203473.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

export default function Login() {
  const nav = useNavigate();
  const location = useLocation();
  const { loginJwt, registerJwt } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", name: "", role: "staff" });

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await loginJwt(form.email, form.password);
      toast.success(`Welcome, ${u.name}`);
      const fallback = ["owner", "admin"].includes(u.role) ? "/admin" : "/staff";
      nav(location.state?.from?.pathname || fallback);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await registerJwt(form);
      toast.success("Account created");
      nav(["owner", "admin"].includes(u.role) ? "/admin" : "/staff");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-caos-bone">
      <div className="relative hidden md:block">
        <img src={AUTH_IMG} alt="ECG" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-caos-forest/85" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12 text-white">
          <Link to="/" data-testid="login-back-home" className="text-2xl">
            <span className="font-display font-bold tracking-tighter">CAOS</span>
            <span className="font-display font-light">Care</span>
          </Link>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.22em] opacity-70">Staff & admin portal</p>
            <h2 className="font-display text-4xl md:text-5xl font-light tracking-tight mt-4 leading-tight">
              Every alert, every resident, every zone — in one calm view.
            </h2>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 md:p-12">
        <div className="w-full max-w-md">
          <h1 className="font-display text-3xl font-medium text-caos-forest">Welcome back</h1>
          <p className="text-caos-mute mt-2">Sign in to CAOS Care staff dashboard.</p>

          <Tabs defaultValue="login" className="mt-8">
            <TabsList className="grid grid-cols-2 w-full">
              <TabsTrigger value="login" data-testid="tab-login">Sign in</TabsTrigger>
              <TabsTrigger value="register" data-testid="tab-register">Register</TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="mt-6">
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <Label htmlFor="login-email" className="font-semibold">Email</Label>
                  <Input
                    id="login-email"
                    type="email"
                    required
                    data-testid="login-email-input"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="mt-1"
                    placeholder="nurse@caoscare.com"
                  />
                </div>
                <div>
                  <Label htmlFor="login-password" className="font-semibold">Password</Label>
                  <Input
                    id="login-password"
                    type="password"
                    required
                    data-testid="login-password-input"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <Button
                  type="submit"
                  disabled={loading}
                  data-testid="login-submit-btn"
                  className="w-full bg-caos-forest hover:bg-caos-forest-hover text-white h-11 rounded-full"
                >
                  {loading ? "Signing in..." : "Sign in"}
                </Button>
              </form>

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-caos-line" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-caos-bone px-2 text-caos-mute tracking-widest">or</span>
                </div>
              </div>

              <GoogleSignIn portal="staff" />

              <div className="mt-6 text-sm text-caos-mute bg-caos-ambient rounded-xl p-4">
                <p className="font-semibold text-caos-forest">Need administrator access?</p>
                <p className="mt-1 text-xs">Use the administrator portal for owner and admin accounts.</p>
                <Link
                  to="/admin-login"
                  data-testid="login-to-admin-link"
                  className="inline-block mt-3 text-xs font-bold uppercase tracking-[0.22em] text-caos-forest hover:text-caos-forest-hover underline"
                >
                  Administrator sign-in →
                </Link>
              </div>
            </TabsContent>

            <TabsContent value="register" className="mt-6">
              <form onSubmit={handleRegister} className="space-y-4">
                <div>
                  <Label htmlFor="reg-name" className="font-semibold">Full name</Label>
                  <Input
                    id="reg-name"
                    required
                    data-testid="register-name-input"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="reg-email" className="font-semibold">Email</Label>
                  <Input
                    id="reg-email"
                    type="email"
                    required
                    data-testid="register-email-input"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="reg-password" className="font-semibold">Password</Label>
                  <Input
                    id="reg-password"
                    type="password"
                    required
                    minLength={6}
                    data-testid="register-password-input"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <Button
                  type="submit"
                  disabled={loading}
                  data-testid="register-submit-btn"
                  className="w-full bg-caos-forest hover:bg-caos-forest-hover text-white h-11 rounded-full"
                >
                  {loading ? "Creating..." : "Create account"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
