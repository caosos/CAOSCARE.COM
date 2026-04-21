import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { toast } from "sonner";

const AUTH_IMG =
  "https://images.pexels.com/photos/6203473/pexels-photo-6203473.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

export default function Login() {
  const nav = useNavigate();
  const { loginJwt, registerJwt } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", name: "", role: "staff" });

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await loginJwt(form.email, form.password);
      toast.success(`Welcome, ${u.name}`);
      nav(["owner", "admin"].includes(u.role) ? "/admin" : "/staff");
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

  const googleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/staff";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-caos-bone">
      {/* Left: image */}
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

      {/* Right: form */}
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

              <Button
                type="button"
                onClick={googleLogin}
                data-testid="google-login-btn"
                variant="outline"
                className="w-full h-11 rounded-full border-2"
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 48 48">
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                </svg>
                Continue with Google
              </Button>

              <div className="mt-6 text-sm text-caos-mute bg-caos-ambient rounded-xl p-4">
                <p className="font-semibold text-caos-forest">Demo staff credentials</p>
                <p className="mt-1">Staff: <span className="font-mono">nurse@caoscare.com / nurse1234</span></p>
                <p className="mt-1 text-xs">Admin nurse + Owner sign in at the admin portal →</p>
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
