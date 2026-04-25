import React, { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  ArrowLeft, Copy, CheckCircle2, Smartphone, Monitor, Apple, Radio, Loader2, RefreshCw, QrCode, AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

// Onboarding wizard for the RF Bridge daemon. Walks an admin (or installer)
// through getting the Nooelec SDR + bridge running on:
//   • Android tablet (Termux + rtl_433 + Python script)
//   • Linux/Mac (apt/brew + rtl_433 + Python)
//   • iOS / unknown — explains why it can't host SDR
// All commands are pre-filled with the kiosk's id, secret, and API URL —
// no typing required. Final step listens for a real pendant press.

function detectOs() {
  const ua = (typeof navigator !== "undefined" ? navigator.userAgent : "") || "";
  if (/android/i.test(ua)) return "android";
  if (/(iphone|ipad|ipod)/i.test(ua)) return "ios";
  if (/macintosh|mac os x/i.test(ua)) return "mac";
  if (/linux/i.test(ua)) return "linux";
  if (/windows/i.test(ua)) return "windows";
  return "unknown";
}

export default function InstallKioskWizard() {
  const { user, loading } = useAuth();
  const nav = useNavigate();
  const { kioskId: paramKioskId } = useParams();

  const [kiosks, setKiosks] = useState([]);
  const [kioskId, setKioskId] = useState(paramKioskId || "");
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const os = useMemo(detectOs, []);

  useEffect(() => {
    api.get("/kiosks").then((r) => setKiosks(r.data)).catch(() => toast.error("Failed to load kiosks"));
  }, []);

  useEffect(() => {
    if (!kioskId) { setInfo(null); return; }
    setBusy(true);
    api.get(`/rf/kiosk/${kioskId}/install-info`)
      .then((r) => setInfo(r.data))
      .catch((err) => toast.error(err?.response?.data?.detail || "Failed to load install info"))
      .finally(() => setBusy(false));
  }, [kioskId]);

  const regenerate = async () => {
    if (!window.confirm("Rotate this kiosk's secret? Any bridge already running with the old secret will need to be re-paired.")) return;
    try {
      await api.post(`/rf/kiosk/${kioskId}/regenerate-secret`);
      const { data } = await api.get(`/rf/kiosk/${kioskId}/install-info`);
      setInfo(data);
      toast.success("Secret rotated.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to rotate secret");
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center bg-caos-bone"><Loader2 className="w-10 h-10 animate-spin text-caos-forest" /></div>;
  if (!user) return <Navigate to="/admin-login" replace />;
  if (!["owner", "admin"].includes(user.role)) return <Navigate to="/staff" replace />;

  return (
    <div className="min-h-screen bg-caos-bone" data-testid="install-wizard-root">
      <header className="border-b border-caos-line px-6 md:px-12 py-6 sticky top-0 z-30 bg-caos-bone/80 backdrop-blur">
        <div className="max-w-5xl mx-auto flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Link to="/admin" className="text-xl inline-flex items-center gap-2" data-testid="install-back-link">
              <ArrowLeft className="w-4 h-4 text-caos-forest" />
              <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
              <span className="font-display font-light text-caos-forest">Care</span>
            </Link>
            <Badge className="bg-caos-forest text-white uppercase tracking-[0.22em] text-[10px] font-bold">Bridge Install</Badge>
          </div>
          <OsBadge os={os} />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 md:px-12 py-10 space-y-8">
        <section>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-3">Step 1 — Pick a kiosk</p>
          <h1 className="font-display text-4xl font-light text-caos-forest leading-tight">
            Install the RF Bridge.
          </h1>
          <p className="text-caos-mute mt-2 max-w-xl">
            The bridge listens to your Nooelec SDR and forwards every pendant press to CAOS Care.
            Pick which kiosk this device belongs to, and the rest is copy-paste.
          </p>
          <div className="mt-5 flex items-center gap-3">
            <Select value={kioskId} onValueChange={(v) => { setKioskId(v); nav(`/admin/install/${v}`); }}>
              <SelectTrigger className="w-[320px]" data-testid="install-kiosk-picker"><SelectValue placeholder="Choose a kiosk" /></SelectTrigger>
              <SelectContent>
                {kiosks.map((k) => <SelectItem key={k.kiosk_id} value={k.kiosk_id}>{k.name} · Rm {k.room}</SelectItem>)}
              </SelectContent>
            </Select>
            {info && (
              <Button variant="outline" size="sm" onClick={regenerate} data-testid="install-rotate-secret">
                <RefreshCw className="w-3.5 h-3.5 mr-2" /> Rotate secret
              </Button>
            )}
          </div>
        </section>

        {busy && <div className="py-12 text-center"><Loader2 className="w-8 h-8 animate-spin text-caos-forest mx-auto" /></div>}

        {info && !busy && (
          <>
            <section data-testid="install-step-2">
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-2">Step 2 — Plug in the Nooelec</p>
              <Card className="p-5 border-caos-line">
                <ol className="space-y-2 text-sm text-caos-ink/90 list-decimal pl-5">
                  <li>Plug your Nooelec NESDR SMArt v5 into the UGREEN USB-OTG hub.</li>
                  <li>Plug the hub into the tablet's USB-C port (also keep the tablet's charger on the hub if it has pass-through).</li>
                  <li>You should see the Nooelec's blue LED come on.</li>
                </ol>
              </Card>
            </section>

            {os === "android" && <AndroidInstall info={info} />}
            {(os === "linux" || os === "mac") && <UnixInstall info={info} os={os} />}
            {os === "windows" && <WindowsInstall info={info} />}
            {os === "ios" && <IosBlocked />}
            {os === "unknown" && <ManualFallback info={info} />}

            <FinalTest info={info} />
          </>
        )}
      </main>
    </div>
  );
}

function OsBadge({ os }) {
  const map = {
    android: { icon: <Smartphone className="w-3.5 h-3.5" />, label: "Detected: Android" },
    ios:     { icon: <Apple className="w-3.5 h-3.5" />,       label: "Detected: iOS (limited)" },
    mac:     { icon: <Apple className="w-3.5 h-3.5" />,       label: "Detected: macOS" },
    linux:   { icon: <Monitor className="w-3.5 h-3.5" />,     label: "Detected: Linux" },
    windows: { icon: <Monitor className="w-3.5 h-3.5" />,     label: "Detected: Windows" },
    unknown: { icon: <Monitor className="w-3.5 h-3.5" />,     label: "Detected: Other" },
  };
  const m = map[os] || map.unknown;
  return <div className="text-xs uppercase tracking-widest text-caos-mute inline-flex items-center gap-2">{m.icon} {m.label}</div>;
}

function CodeBlock({ children, label, testid }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    try {
      navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy. Long-press to select instead.");
    }
  };
  return (
    <div className="relative group">
      {label && <p className="text-[10px] uppercase tracking-widest text-caos-mute mb-1">{label}</p>}
      <pre
        data-testid={testid}
        className="bg-caos-ink text-caos-bone rounded-lg p-3 overflow-x-auto text-xs font-mono whitespace-pre-wrap break-all"
      >{children}</pre>
      <button
        onClick={copy}
        data-testid={testid ? `${testid}-copy` : undefined}
        className="absolute top-2 right-2 text-[10px] uppercase tracking-widest font-bold px-2 py-1 rounded bg-caos-bone/90 text-caos-forest hover:bg-caos-bone transition-colors"
      >
        {copied ? <CheckCircle2 className="w-3.5 h-3.5 inline" /> : <Copy className="w-3.5 h-3.5 inline" />}
        <span className="ml-1">{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}

function AndroidInstall({ info }) {
  const launchCmd = `CAOS_API_URL='${info.api_url}' \\\nCAOS_KIOSK_ID='${info.kiosk_id}' \\\nCAOS_RF_SECRET='${info.rf_secret}' \\\npython3 caos_rf_bridge.py`;
  return (
    <section data-testid="install-android">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-2">Step 3 — Android setup</p>
      <Card className="p-5 border-caos-line space-y-4">
        <div>
          <p className="font-semibold text-caos-forest">A) Install <a href="https://f-droid.org/packages/com.termux/" target="_blank" rel="noreferrer" className="underline">Termux from F-Droid</a></p>
          <p className="text-caos-mute text-xs mt-1">Don't use the Play Store version — it's outdated and can't access USB.</p>
        </div>

        <div>
          <p className="font-semibold text-caos-forest mb-1">B) Inside Termux, paste this:</p>
          <CodeBlock testid="install-android-pkg">{`pkg install root-repo -y && pkg install rtl-433 python -y && pip install requests`}</CodeBlock>
        </div>

        <div>
          <p className="font-semibold text-caos-forest mb-1">C) Download the bridge daemon:</p>
          <CodeBlock testid="install-android-curl">{`curl -O ${info.api_url}/api/rf/bridge-daemon -o caos_rf_bridge.py`}</CodeBlock>
        </div>

        <div>
          <p className="font-semibold text-caos-forest mb-1">D) Run the bridge — credentials pre-filled:</p>
          <CodeBlock testid="install-android-run">{launchCmd}</CodeBlock>
          <p className="text-[11px] text-caos-mute mt-1">Long-press a pendant button — the bridge logs <code>captured</code> within a second.</p>
        </div>

        <div className="pt-2 border-t border-caos-line">
          <p className="text-xs uppercase tracking-widest text-caos-mute">Want it to survive reboots?</p>
          <p className="text-sm mt-1">Install Termux:Boot from F-Droid and put the launch command in <code>~/.termux/boot/caos.sh</code>. Or wait for the upcoming <b>CAOS Care Companion APK</b> — one-tap install, foreground service, no Termux required.</p>
        </div>
      </Card>
    </section>
  );
}

function UnixInstall({ info, os }) {
  const installCmd = os === "mac"
    ? `brew install rtl-sdr rtl_433 python3 && pip3 install requests`
    : `sudo apt-get update && sudo apt-get install -y rtl-sdr rtl-433 python3-requests`;
  const launchCmd = `CAOS_API_URL='${info.api_url}' \\\nCAOS_KIOSK_ID='${info.kiosk_id}' \\\nCAOS_RF_SECRET='${info.rf_secret}' \\\npython3 caos_rf_bridge.py`;
  return (
    <section data-testid="install-unix">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-2">Step 3 — {os === "mac" ? "macOS" : "Linux"} setup</p>
      <Card className="p-5 border-caos-line space-y-4">
        <div>
          <p className="font-semibold text-caos-forest mb-1">A) Install dependencies:</p>
          <CodeBlock testid="install-unix-deps">{installCmd}</CodeBlock>
        </div>
        <div>
          <p className="font-semibold text-caos-forest mb-1">B) Get the bridge daemon:</p>
          <CodeBlock testid="install-unix-curl">{`curl -o caos_rf_bridge.py ${info.api_url}/api/rf/bridge-daemon`}</CodeBlock>
        </div>
        <div>
          <p className="font-semibold text-caos-forest mb-1">C) Launch — credentials pre-filled:</p>
          <CodeBlock testid="install-unix-run">{launchCmd}</CodeBlock>
        </div>
      </Card>
    </section>
  );
}

function WindowsInstall({ info }) {
  return (
    <section data-testid="install-windows">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-2">Step 3 — Windows setup</p>
      <Card className="p-5 border-caos-line space-y-3">
        <p>Windows works but needs the Zadig USB driver swap before the SDR is visible. Easiest path:</p>
        <ol className="list-decimal pl-5 text-sm space-y-1">
          <li>Install <a className="underline" href="https://zadig.akeo.ie/" target="_blank" rel="noreferrer">Zadig</a> → swap the Nooelec driver to WinUSB.</li>
          <li>Install <a className="underline" href="https://www.python.org/downloads/" target="_blank" rel="noreferrer">Python 3.11+</a> and <a className="underline" href="https://github.com/merbanan/rtl_433/releases" target="_blank" rel="noreferrer">rtl_433 for Windows</a>.</li>
          <li>Run the bridge with the same env-vars below.</li>
        </ol>
        <CodeBlock testid="install-windows-run">{`set CAOS_API_URL=${info.api_url}\nset CAOS_KIOSK_ID=${info.kiosk_id}\nset CAOS_RF_SECRET=${info.rf_secret}\npython caos_rf_bridge.py`}</CodeBlock>
      </Card>
    </section>
  );
}

function IosBlocked() {
  return (
    <section data-testid="install-ios-blocked">
      <Card className="p-5 border-caos-amber bg-caos-amber/10">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-caos-amber mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold text-caos-forest">iOS can't host the Nooelec.</p>
            <p className="text-sm text-caos-ink/80 mt-1">Apple doesn't expose USB-host APIs to apps for arbitrary devices. Use a separate Android tablet (any cheap $80 unit works), a Raspberry Pi, or a Mac for this room's bridge. The web app you're reading this on can stay on iOS.</p>
          </div>
        </div>
      </Card>
    </section>
  );
}

function ManualFallback({ info }) {
  return (
    <section data-testid="install-manual">
      <Card className="p-5 border-caos-line">
        <p className="text-sm text-caos-ink/80">We couldn't auto-detect your OS, but the bridge runs anywhere Python + rtl_433 do. Use the Linux instructions as a base and adapt.</p>
        <CodeBlock testid="install-manual-info">{JSON.stringify({ api_url: info.api_url, kiosk_id: info.kiosk_id, rf_secret: info.rf_secret }, null, 2)}</CodeBlock>
      </Card>
    </section>
  );
}

function FinalTest({ info }) {
  const [events, setEvents] = useState([]);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    if (!polling) return;
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/rf/events?limit=10`);
        setEvents(data.filter((e) => e.kiosk_id === info.kiosk_id));
      } catch { /* ignore */ }
    }, 1500);
    return () => clearInterval(t);
  }, [polling, info.kiosk_id]);

  return (
    <section data-testid="install-final-test">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-2">Step 4 — Final test</p>
      <Card className="p-5 border-caos-line space-y-4">
        <p className="text-sm">With the bridge running, press a pendant. We'll show every press received here in real time.</p>
        <div className="flex items-center gap-3">
          <Button
            onClick={() => setPolling((v) => !v)}
            data-testid="install-test-toggle"
            className={polling ? "bg-caos-terracotta hover:bg-caos-terracotta-dark rounded-full" : "bg-caos-forest rounded-full"}
          >
            <Radio className="w-4 h-4 mr-2" />
            {polling ? "Stop listening" : "Start listening"}
          </Button>
          <p className="text-xs text-caos-mute">{polling ? "Live · poll every 1.5s" : "Idle"}</p>
        </div>
        {polling && events.length === 0 && (
          <p className="text-caos-mute italic text-sm">Nothing yet. Press a pendant — the event lands here within a second.</p>
        )}
        <div className="space-y-1.5 max-h-72 overflow-y-auto">
          {events.map((e, i) => (
            <div key={`${e.received_at}-${i}`} data-testid={`install-event-${i}`} className={`text-sm flex items-center gap-2 px-2 py-1.5 rounded ${e.matched_device_id ? "bg-caos-forest/5" : "bg-caos-amber/10"}`}>
              {e.matched_device_id ? <CheckCircle2 className="w-3.5 h-3.5 text-caos-forest" /> : <QrCode className="w-3.5 h-3.5 text-caos-amber" />}
              <span className="font-mono text-xs">{(e.fingerprint?.frequency_hz / 1_000_000).toFixed(3)} MHz</span>
              <span className="text-caos-mute text-xs">·</span>
              <span className="text-xs">{e.matched_device_id ? `matched (${e.match_score})` : "unmatched — open Add new pendant in RF tab to pair this"}</span>
              <span className="ml-auto text-xs text-caos-mute">{new Date(e.received_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
        <div className="pt-3 border-t border-caos-line text-xs text-caos-mute">
          Once the bridge is running and you see events here, head back to <Link to="/admin" className="underline text-caos-forest">the dashboard</Link> → <b>RF Pendants</b> tab and pair each pendant.
        </div>
      </Card>
    </section>
  );
}
