import React from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Card } from "../components/ui/card";
import { ArrowLeft, BookOpen } from "lucide-react";
import { TutorialVideo } from "./TutorialVideo";

// /admin/help — the tutorial hub. Lists every walkthrough with a poster
// and a script preview. Videos can land here as MP4 files (or YouTube
// embeds via a `src` swap). Until they're recorded, the script preview
// gives reviewers and the product owner clarity on what's coming.

const TUTORIALS = [
  {
    id: "add-pendant",
    title: "Add a new pendant in 60 seconds",
    duration: "60s",
    script: `Open Admin → RF Pendants → Add new pendant.\n` +
            `Pick the kiosk nearest the pendant.\n` +
            `Press the pendant button. The captured signal appears.\n` +
            `Type a label like "Margaret's bedside" and bind to the resident.\n` +
            `Save. From now on, every press fires an alert automatically.`,
  },
  {
    id: "test-pendant",
    title: "Test a paired pendant",
    duration: "30s",
    script: `Find the pendant in the RF Pendants table.\n` +
            `Click the Test button.\n` +
            `Press the pendant. Pass/fail score appears in real time.`,
  },
  {
    id: "first-bridge-install",
    title: "First-time bridge install on an Android tablet",
    duration: "90s",
    script: `Open Admin → RF Pendants → Install bridge.\n` +
            `Pick the kiosk this tablet will serve.\n` +
            `Install Termux from F-Droid (NOT Play Store).\n` +
            `Paste the pre-filled commands. The Nooelec starts listening.\n` +
            `Step 4 confirms with a live RF event feed.`,
  },
  {
    id: "qr-pair-tablet",
    title: "Pair a tablet with QR code (Companion APK)",
    duration: "60s",
    script: `Open the CAOS Care Companion APK on the tablet.\n` +
            `Tap "Scan provisioning code".\n` +
            `Open Admin → RF Pendants → Install bridge → Show QR.\n` +
            `Hold the tablet camera over the QR. Bridge starts in 2s.`,
  },
  {
    id: "what-happens-on-press",
    title: "What happens when Margaret presses her button",
    duration: "90s",
    script: `Pendant press → SDR captures → fingerprint matched.\n` +
            `Alert created in the database.\n` +
            `Staff smartwatch / dashboard notified.\n` +
            `Kiosk in the room asks how it can help, full duplex voice.\n` +
            `When staff arrives and resolves, registry records who, what, how long.`,
  },
  {
    id: "voice-experience",
    title: "What CAOS sounds like to a resident",
    duration: "90s",
    script: `Resident perspective. CAOS speaks softly, by name.\n` +
            `It already knows recent moments and durable facts.\n` +
            `Resident can interrupt anytime — chime-in just adds context.\n` +
            `When help arrives, CAOS gracefully steps back. No goodbyes, just calm.`,
  },
  {
    id: "hardware-receipts",
    title: "Run a compatibility probe on new hardware",
    duration: "60s",
    script: `Admin → Hardware → Register device.\n` +
            `Pick the device class (kiosk tablet, hub, speaker, etc.).\n` +
            `Click Probe. Mark each capability pass/fail.\n` +
            `Receipt is issued. If pass, role can be assigned. If fail, no role.`,
  },
  {
    id: "memory-bulletin",
    title: "Editing a resident's memory bulletin",
    duration: "60s",
    script: `Admin → Blueprint → scroll to the bulletin.\n` +
            `Click any fact or event to edit inline.\n` +
            `Pin the things CAOS should never forget.\n` +
            `Archive the things that no longer apply.`,
  },
];

export default function HelpHub() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/admin-login" replace />;
  if (!["owner", "admin"].includes(user.role)) return <Navigate to="/staff" replace />;

  return (
    <div className="min-h-screen bg-caos-bone" data-testid="help-hub">
      <header className="border-b border-caos-line px-6 md:px-12 py-6 sticky top-0 z-30 bg-caos-bone/80 backdrop-blur">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <Link to="/admin" className="text-xl inline-flex items-center gap-2" data-testid="help-back">
            <ArrowLeft className="w-4 h-4 text-caos-forest" />
            <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
            <span className="font-display font-light text-caos-forest">Care</span>
          </Link>
          <span className="text-caos-mute text-sm">· Tutorials</span>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 md:px-12 py-10 space-y-8">
        <section>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-3">Help · Walkthrough videos</p>
          <h1 className="font-display text-4xl font-light text-caos-forest leading-tight">Watch, don't read.</h1>
          <p className="text-caos-mute mt-2 max-w-xl">
            Care staff are mid-shift, interrupted, and don't read documentation.
            Every important flow has a 60-90s video here.
          </p>
        </section>

        <Card className="p-5 border-caos-line">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-4">
            <BookOpen className="w-4 h-4 text-caos-forest" /> All walkthroughs
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {TUTORIALS.map((t) => (
              <TutorialVideo key={t.id} {...t} testid={`help-${t.id}`} />
            ))}
          </div>
          <p className="text-[11px] text-caos-mute mt-4 italic">
            Videos appear here once recorded. Until then, each card shows the script so you can review the planned narration.
          </p>
        </Card>
      </main>
    </div>
  );
}
