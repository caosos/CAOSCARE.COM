import React, { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  ShieldCheck, Brain, Radio, Sparkles, Watch, Glasses, Lightbulb, Cpu,
  Stethoscope, Heart, Lock, Layers, ArrowLeft, Users, AlertTriangle,
  Calendar, Pin, Archive,
} from "lucide-react";
import { toast } from "sonner";

// ——— The Blueprint. Owner-only. ——————————————————————————————————————————
// This is the single source of truth for where CAOS Care is going. Every
// decision — memory shape, hardware stack, role tiers, AI behaviour — is
// documented here so the vision survives context windows, forks, and handoffs.

export default function Blueprint() {
  const { user, loading } = useAuth();
  const nav = useNavigate();

  if (loading) return <div className="min-h-screen flex items-center justify-center bg-caos-bone"><div className="w-12 h-12 rounded-full bg-caos-forest caos-orb" /></div>;
  if (!user) return <Navigate to="/admin-login" replace />;
  if (user.role !== "owner") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-caos-bone p-8">
        <Card className="max-w-md p-8 text-center border-caos-line" data-testid="blueprint-denied">
          <Lock className="w-10 h-10 text-caos-terracotta mx-auto" />
          <h1 className="font-display text-2xl text-caos-forest mt-3">Owner only</h1>
          <p className="text-caos-mute mt-2">
            The Blueprint is visible only to the CAOS Care system owner.
            Clinical admins and staff don't see this page.
          </p>
          <Button onClick={() => nav("/admin")} className="mt-5 bg-caos-forest rounded-full" data-testid="blueprint-back-admin">
            Back to admin
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-caos-bone" data-testid="blueprint-root">
      <Header />
      <main className="max-w-5xl mx-auto px-6 md:px-12 py-10 space-y-14">
        <Hero />
        <RoleTiers />
        <MemoryArchitecture />
        <MemoryBulletin />
        <HardwareStack />
        <AILayers />
        <ClinicianRegistry />
        <FamilyCompliance />
        <RoadmapFooter />
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className="border-b border-caos-line px-6 md:px-12 py-6 bg-caos-bone sticky top-0 z-30 backdrop-blur">
      <div className="max-w-5xl mx-auto flex items-center justify-between flex-wrap gap-3">
        <Link to="/admin" data-testid="blueprint-back-link" className="text-xl inline-flex items-center gap-2">
          <ArrowLeft className="w-4 h-4 text-caos-forest" />
          <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
          <span className="font-display font-light text-caos-forest">Care</span>
          <Badge className="ml-2 bg-caos-terracotta text-white uppercase tracking-[0.22em] text-[10px] font-bold">Blueprint</Badge>
        </Link>
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-caos-mute">
          <ShieldCheck className="w-4 h-4 text-caos-forest" /> Owner-only document
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="caos-fade-in" data-testid="blueprint-hero">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-3">Vision · Living document</p>
      <h1 className="font-display text-5xl md:text-7xl font-light tracking-tighter text-caos-forest leading-[1.02]">
        Not a chatbot.
        <br />
        <span className="text-caos-terracotta">A lifelong companion.</span>
      </h1>
      <p className="text-caos-mute text-lg mt-6 max-w-2xl leading-relaxed">
        CAOS Care is the operating system for a senior living facility. One calm
        AI per resident, learning them for years — supported by pendants,
        wearables, vision glasses, smart-room devices, and a clinician-grade
        event registry. This page is the full architecture as it lives today.
      </p>
    </section>
  );
}

function Section({ icon: Icon, eyebrow, title, subtitle, children, testid }) {
  return (
    <section data-testid={testid} className="caos-fade-in">
      <div className="flex items-start gap-4 mb-5">
        <div className="w-12 h-12 rounded-2xl bg-caos-forest/10 flex items-center justify-center shrink-0">
          <Icon className="w-6 h-6 text-caos-forest" />
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute">{eyebrow}</p>
          <h2 className="font-display text-3xl md:text-4xl font-light tracking-tight text-caos-forest leading-tight mt-1">
            {title}
          </h2>
          {subtitle && <p className="text-caos-mute mt-2 max-w-2xl">{subtitle}</p>}
        </div>
      </div>
      <div>{children}</div>
    </section>
  );
}

function RoleTiers() {
  const tiers = [
    {
      role: "Owner",
      who: "You — the system owner",
      sees: ["Blueprint (this page)", "Memory bulletin (both bins) per resident", "Architecture + override", "Full audit + system debug"],
      color: "#B6463A",
      testid: "tier-owner",
    },
    {
      role: "Admin (admin nurse)",
      who: "Clinical leadership at the facility",
      sees: ["Residents, alerts, insights", "Clinician event registry", "Audit exports (CSV)", "Tasks, devices, family contacts"],
      color: "#4A7C59",
      testid: "tier-admin",
    },
    {
      role: "Staff",
      who: "Nurses, aides, on-shift team",
      sees: ["Staff dashboard", "Acknowledge + close events", "My tasks", "Assigned residents only"],
      color: "#7A6B56",
      testid: "tier-staff",
    },
  ];
  return (
    <Section
      icon={Users}
      eyebrow="Access tiers"
      title="Three roles, three doors."
      subtitle="Owner is above admin. Admin (clinical admin / admin nurse) runs the facility. Staff run the shift."
      testid="blueprint-roles"
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {tiers.map((t) => (
          <Card key={t.role} data-testid={t.testid} className="p-5 border-caos-line bg-white" style={{ borderTopWidth: 4, borderTopColor: t.color }}>
            <p className="font-display text-2xl text-caos-forest">{t.role}</p>
            <p className="text-caos-mute text-sm mt-1">{t.who}</p>
            <ul className="mt-4 space-y-1.5 text-sm text-caos-ink/80">
              {t.sees.map((s) => <li key={s} className="flex gap-2"><span className="text-caos-forest">·</span>{s}</li>)}
            </ul>
          </Card>
        ))}
      </div>
    </Section>
  );
}

function MemoryArchitecture() {
  return (
    <Section
      icon={Brain}
      eyebrow="Memory"
      title="One thread per resident. For life."
      subtitle="CAOS runs on a large-context model. We never arbitrarily cut history. Instead, conversations flow through a hydration pipeline that keeps important things present and lets throwaway chatter fade."
      testid="blueprint-memory"
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-6 border-caos-line bg-white" data-testid="mem-rolling">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Rolling window</p>
          <h3 className="font-display text-2xl text-caos-forest mt-1">Live conversation</h3>
          <p className="text-caos-ink/80 mt-3 text-sm leading-relaxed">
            Every turn is stored in <code className="text-xs bg-caos-ambient px-1.5 py-0.5 rounded">db.conversations</code> and
            replayed into Claude each response. Today the rolling window is <b>500 turns / session-scoped</b>, which fits
            comfortably inside the model's context budget and covers even the longest same-day visit.
          </p>
        </Card>
        <Card className="p-6 border-caos-line bg-white" data-testid="mem-sanitize">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Sanitize</p>
          <h3 className="font-display text-2xl text-caos-forest mt-1">Session scoping</h3>
          <p className="text-caos-ink/80 mt-3 text-sm leading-relaxed">
            Chat context is scoped to the current <b>session_id</b>. That's what keeps a past fall from
            bleeding into today's bathroom request. The long-term identity still lives in the bins below.
          </p>
        </Card>
        <Card className="p-6 border-caos-line bg-white" data-testid="mem-dehydrate">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Dehydrate</p>
          <h3 className="font-display text-2xl text-caos-forest mt-1">Haiku extractor</h3>
          <p className="text-caos-ink/80 mt-3 text-sm leading-relaxed">
            After every exchange, a background Claude Haiku 4.5 call reads the turn and proposes durable
            facts. It auto-sorts each fact into one of two bins, dedupes against near-identical prior rows,
            and writes them to <code className="text-xs bg-caos-ambient px-1.5 py-0.5 rounded">db.memories</code>.
          </p>
        </Card>
        <Card className="p-6 border-caos-line bg-white" data-testid="mem-hydrate">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Hydrate</p>
          <h3 className="font-display text-2xl text-caos-forest mt-1">Per-turn injection</h3>
          <p className="text-caos-ink/80 mt-3 text-sm leading-relaxed">
            Every chat turn builds a fresh context:
            <span className="block mt-2 p-2 bg-caos-ambient rounded-lg font-mono text-xs">
              pinned facts · top-40 Personal Facts · top-25 Life Events · rolling 500-turn window
            </span>
            The AI sees identity + recent moments + live conversation — together.
          </p>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-6 border-2 border-caos-forest bg-white" data-testid="bin-facts">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-caos-forest" />
            <h3 className="font-display text-2xl text-caos-forest">Personal Facts bin</h3>
          </div>
          <p className="text-caos-mute text-sm mt-1">Durable identity. Pinned first, then importance.</p>
          <ul className="mt-3 space-y-1 text-sm text-caos-ink/80">
            <li>· family — names, relationships, caregivers</li>
            <li>· preferences — foods, shows, music, routines</li>
            <li>· health — allergies, conditions, non-negotiables</li>
            <li>· history — past jobs, places, keepsakes</li>
            <li>· daily_pattern — sleep, walks, meds timing</li>
            <li>· relationship — friends, pets, staff bonds</li>
          </ul>
        </Card>
        <Card className="p-6 border-2 border-caos-terracotta bg-white" data-testid="bin-events">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-caos-terracotta" />
            <h3 className="font-display text-2xl text-caos-forest">Life Events bin</h3>
          </div>
          <p className="text-caos-mute text-sm mt-1">Dated moments. Pinned first, then newest.</p>
          <ul className="mt-3 space-y-1 text-sm text-caos-ink/80">
            <li>· milestone — birthdays, anniversaries, visits</li>
            <li>· concern — falls, fears, losses</li>
            <li>· other — conversations that mattered</li>
          </ul>
          <p className="text-xs text-caos-mute mt-3 italic">Each row has <code>event_at</code> so the bulletin renders chronologically.</p>
        </Card>
      </div>

      <Card className="mt-6 p-5 border-caos-line bg-caos-ambient/60">
        <div className="flex items-start gap-3">
          <Pin className="w-5 h-5 text-caos-amber mt-0.5" />
          <div className="text-sm text-caos-ink/80">
            <p className="font-semibold text-caos-forest mb-1">Pinned rows never drop.</p>
            <p>Admins can pin anything — a fact ("Frank's dog Bruno died") or an event ("daughter visits every Sunday"). Pinned rows are injected first, regardless of importance or recency. An <Archive className="inline w-3.5 h-3.5" /> <code className="text-xs bg-white px-1 rounded">archived</code> flag retires rows that are no longer relevant without deleting history.</p>
          </div>
        </div>
      </Card>
    </Section>
  );
}

function MemoryBulletin() {
  const [residents, setResidents] = useState([]);
  const [selected, setSelected] = useState("");
  const [bulletin, setBulletin] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/residents");
        setResidents(data);
        if (data.length) setSelected(data[0].resident_id);
      } catch { toast.error("Could not load residents"); }
    })();
  }, []);

  useEffect(() => {
    if (!selected) return;
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/memory/bulletin/${selected}`);
        setBulletin(data);
      } catch (err) {
        toast.error(err?.response?.data?.detail || "Bulletin load failed");
      } finally { setLoading(false); }
    })();
  }, [selected]);

  return (
    <Section
      icon={Sparkles}
      eyebrow="Live bulletin"
      title="The bulletin — what CAOS knows, right now."
      subtitle="Pick a resident to read the state of their memory. Owner sees both bins plus the rolling-window meter."
      testid="blueprint-bulletin"
    >
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={selected} onValueChange={setSelected}>
          <SelectTrigger className="w-[280px]" data-testid="bulletin-resident-picker"><SelectValue placeholder="Pick a resident" /></SelectTrigger>
          <SelectContent>
            {residents.map((r) => (
              <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Rm {r.room}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {bulletin && (
          <div className="text-xs text-caos-mute uppercase tracking-wider">
            <span className="font-mono font-bold text-caos-forest">{bulletin.conversation_turns}</span> turns logged ·
            rolling window <span className="font-mono font-bold text-caos-forest">{bulletin.rolling_window}</span>
          </div>
        )}
      </div>

      {loading && <div className="text-center py-8 text-caos-mute">Loading bulletin…</div>}

      {bulletin && !loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <BinColumn
            title="Personal Facts"
            color="#4A7C59"
            icon={<Layers className="w-5 h-5" />}
            rows={bulletin.facts}
            empty="No personal facts yet. Bins populate after conversations."
            testid="bulletin-facts-col"
          />
          <BinColumn
            title="Life Events"
            color="#B6463A"
            icon={<Calendar className="w-5 h-5" />}
            rows={bulletin.events}
            empty="No life events yet. Significant moments will land here."
            testid="bulletin-events-col"
          />
        </div>
      )}
    </Section>
  );
}

function BinColumn({ title, color, icon, rows, empty, testid }) {
  return (
    <Card className="p-5 border-caos-line bg-white" data-testid={testid} style={{ borderTopWidth: 4, borderTopColor: color }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-caos-forest">
          {icon}<h3 className="font-display text-xl">{title}</h3>
        </div>
        <Badge variant="outline" className="uppercase text-xs tracking-wider">{rows.length} rows</Badge>
      </div>
      <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
        {rows.map((m) => (
          <div key={m.memory_id} data-testid={`bulletin-row-${m.memory_id}`} className="text-sm bg-caos-ambient/40 rounded-lg px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <p className="text-caos-ink leading-snug flex-1">
                {m.pinned && <Pin className="inline w-3.5 h-3.5 text-caos-amber mr-1 -mt-0.5" />}
                {m.archived && <Archive className="inline w-3.5 h-3.5 text-caos-mute mr-1 -mt-0.5" />}
                {m.text}
              </p>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wider shrink-0">
                i{m.importance}
              </Badge>
            </div>
            <div className="text-[10px] text-caos-mute uppercase tracking-wider mt-1">
              {m.category?.replace("_", " ")} · {m.source}
              {m.event_at && ` · ${m.event_at.slice(0, 10)}`}
              {m.times_referenced ? ` · ref ${m.times_referenced}×` : ""}
            </div>
          </div>
        ))}
        {rows.length === 0 && <p className="text-caos-mute italic text-sm text-center py-6">{empty}</p>}
      </div>
    </Card>
  );
}

function HardwareStack() {
  const layers = [
    { icon: Cpu, title: "Room kiosk (tablet)", body: "The companion orb. Continuous voice loop, barge-in VAD, TV auto-mute, [REST] sleep tag, 11 OpenAI voices.", testid: "hw-kiosk" },
    { icon: Radio, title: "900 MHz pendants", body: "Philips Lifeline-style buttons. Android bridge + RTL-SDR decodes presses, POSTs /api/pendants/event with zone + battery.", testid: "hw-pendants" },
    { icon: Watch, title: "Wearables", body: "Smartwatches, earbuds, BLE beacons. Fall, heart-rate, inactivity events feed clinical thresholds per resident.", testid: "hw-wearables" },
    { icon: Glasses, title: "AI-vision glasses (Vuzix M400)", body: "For visually impaired residents. Scene description, wayfinding, medication-label reading.", testid: "hw-vision" },
    { icon: Lightbulb, title: "Smart-room devices", body: "Lights, fans, heaters, AC, TVs, locks. Commands queue at /api/devices/queue/{room} — the bridge tablet executes locally.", testid: "hw-smartroom" },
  ];
  return (
    <Section
      icon={Radio}
      eyebrow="Hardware"
      title="The physical stack."
      subtitle="Every layer hangs off the Kiosk tablet. One hub per room."
      testid="blueprint-hardware"
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {layers.map((l) => (
          <Card key={l.title} data-testid={l.testid} className="p-4 border-caos-line bg-white flex gap-3">
            <l.icon className="w-5 h-5 text-caos-forest shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-caos-forest">{l.title}</p>
              <p className="text-caos-mute text-sm">{l.body}</p>
            </div>
          </Card>
        ))}
      </div>
    </Section>
  );
}

function AILayers() {
  return (
    <Section
      icon={Sparkles}
      eyebrow="AI"
      title="The AI stack."
      subtitle="Claude drives the voice. OpenAI does ears and mouth. Haiku does bookkeeping."
      testid="blueprint-ai"
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card className="p-4 border-caos-line bg-white" data-testid="ai-sonnet">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Claude Sonnet 4.5</p>
          <p className="font-display text-lg text-caos-forest mt-1">Companion voice</p>
          <p className="text-sm text-caos-ink/80 mt-2">Primary conversational model. Emits <code className="text-xs bg-caos-ambient px-1 rounded">[REST]</code> when the resident asks for quiet.</p>
        </Card>
        <Card className="p-4 border-caos-line bg-white" data-testid="ai-haiku">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Claude Haiku 4.5</p>
          <p className="font-display text-lg text-caos-forest mt-1">Memory + classifier</p>
          <p className="text-sm text-caos-ink/80 mt-2">Dehydrates turns into bin rows. Auto-classifies every resolved alert (category, summary, response time).</p>
        </Card>
        <Card className="p-4 border-caos-line bg-white" data-testid="ai-openai">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">OpenAI Whisper + TTS</p>
          <p className="font-display text-lg text-caos-forest mt-1">Ears + mouth</p>
          <p className="text-sm text-caos-ink/80 mt-2">Direct SDK, your personal key. 11 voices. Barge-in VAD interrupts TTS on resident speech.</p>
        </Card>
      </div>
    </Section>
  );
}

function ClinicianRegistry() {
  return (
    <Section
      icon={Stethoscope}
      eyebrow="Clinical"
      title="Event registry."
      subtitle="Every pendant press, button, wearable alarm enters the clinician registry. Auto-classified, timed, summarized."
      testid="blueprint-clinical"
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5 border-caos-line bg-white">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">What every alert records</p>
          <ul className="mt-2 space-y-1.5 text-sm text-caos-ink/80">
            <li>· category (bathroom / fall / lonely / pain / confusion / other)</li>
            <li>· resident_stated_reason + ai_summary</li>
            <li>· response_seconds (created → acknowledged)</li>
            <li>· duration_seconds (created → resolved)</li>
            <li>· triggered_by, zone, outcome, close_notes</li>
          </ul>
        </Card>
        <Card className="p-5 border-caos-line bg-white">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Endpoint</p>
          <p className="font-mono text-sm bg-caos-ambient rounded p-2 mt-2">GET /api/residents/{`{id}`}/stats</p>
          <p className="text-sm text-caos-mute mt-3">Returns 30-day category breakdown, avg response time, alert counts. Admin nurses consume this. A dedicated dashboard UI is the next major build.</p>
        </Card>
      </div>
    </Section>
  );
}

function FamilyCompliance() {
  return (
    <Section
      icon={Heart}
      eyebrow="Family + compliance"
      title="The humans outside the building."
      subtitle="Family gets warmth without violating privacy. Auditors get receipts without getting chat content."
      testid="blueprint-family"
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card className="p-4 border-caos-line bg-white">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Family portal</p>
          <p className="text-sm text-caos-ink/80 mt-2">Magic-link view per contact. Last seen, active calls, resolved-this-week. One haiku per night — a 3-line emotional postcard generated by Claude from the bins.</p>
        </Card>
        <Card className="p-4 border-caos-line bg-white">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Audit CSV</p>
          <p className="text-sm text-caos-ink/80 mt-2">Alerts / tasks / pages / medications — full chain-of-custody export for HIPAA reviews. Companion chat content is <b>intentionally excluded</b>.</p>
        </Card>
      </div>
    </Section>
  );
}

function RoadmapFooter() {
  return (
    <Section
      icon={AlertTriangle}
      eyebrow="What's next"
      title="The things still on the table."
      testid="blueprint-next"
    >
      <Card className="p-5 border-caos-line bg-white">
        <ul className="space-y-1.5 text-sm text-caos-ink/80">
          <li>· <b>Clinician Dashboard UI</b> — visualize <code className="text-xs bg-caos-ambient px-1 rounded">/api/residents/{`{id}`}/stats</code> with trend charts.</li>
          <li>· <b>Twilio + Resend</b> — drop in keys, escalation loop unlocks.</li>
          <li>· <b>Pendant decode</b> — IQ capture of a real Philips Lifeline press, Universal Radio Hacker → decoder in the Android bridge.</li>
          <li>· <b>Memory bulletin CRUD</b> — inline pin / archive / edit from this page.</li>
          <li>· <b>Vuzix M400 guidance</b> — visually impaired resident wayfinding loop.</li>
          <li>· <b>Multi-tenant</b> — facility_id on every model; national rollout.</li>
        </ul>
      </Card>
      <p className="text-center text-caos-mute text-xs mt-10">
        © 2026 CAOS Care · Blueprint · This document evolves with the system.
      </p>
    </Section>
  );
}
