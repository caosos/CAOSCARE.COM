import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Heart, MapPin, Shield, CheckCircle2, AlertCircle, Clock } from "lucide-react";
import { toast } from "sonner";

const SEV_COLOR = {
  emergency: "#B6463A",
  assist: "#D28D38",
  comfort: "#4A7C59",
};

function timeAgo(iso) {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function FamilyPortal() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  const fetchSummary = async () => {
    try {
      const { data: d } = await axios.get(`${API}/family-portal/${token}/summary`);
      setData(d);
      setErr(null);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Unable to load");
    }
  };

  useEffect(() => {
    fetchSummary();
    const t = setInterval(fetchSummary, 30000); // refresh every 30s
    return () => clearInterval(t);
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const markRead = async () => {
    try {
      await axios.post(`${API}/family-portal/${token}/acknowledge-read`);
      toast.success("Thanks for checking in");
    } catch {}
  };

  if (err) {
    return (
      <div className="min-h-screen bg-caos-bone flex items-center justify-center p-8">
        <Card className="max-w-md p-8 text-center border-caos-line">
          <AlertCircle className="w-10 h-10 text-caos-terracotta mx-auto" />
          <h1 className="font-display text-2xl text-caos-forest mt-3">Link not valid</h1>
          <p className="text-caos-mute mt-2">{err}. Please ask the facility for a new family link.</p>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-caos-bone flex items-center justify-center">
        <div className="w-12 h-12 rounded-full bg-caos-forest caos-orb" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-caos-bone">
      {/* Header */}
      <header className="border-b border-caos-line px-6 md:px-12 py-6 bg-caos-bone sticky top-0 z-30 backdrop-blur">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <a href="/" className="text-xl">
            <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
            <span className="font-display font-light text-caos-forest">Care</span>
          </a>
          <span className="text-caos-mute text-sm hidden md:block">Family view for {data.contact.name}</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 md:px-12 py-10">
        {/* Greeting */}
        <div className="caos-fade-in">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-2">
            Hi {data.contact.name.split(" ")[0]}
          </p>
          <h1 className="font-display text-4xl md:text-6xl font-light tracking-tighter text-caos-forest leading-[1.05]">
            Here's how {data.resident.name} is doing today.
          </h1>
          <p className="text-caos-mute text-lg mt-4">
            Live view. Updates every 30 seconds. This page shows what the facility has consented to share.
          </p>
        </div>

        {/* Status tiles */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-10">
          <Card className="p-6 border-caos-line bg-white caos-fade-in caos-delay-100">
            <div className="flex items-center gap-2 text-caos-mute text-xs font-bold uppercase tracking-widest">
              <MapPin className="w-3.5 h-3.5" /> Last seen
            </div>
            <p className="font-display text-2xl mt-2 text-caos-forest">{data.last_seen.zone || "Not seen recently"}</p>
            <p className="text-caos-mute text-sm mt-1">{data.last_seen.at ? timeAgo(data.last_seen.at) : "—"}</p>
          </Card>
          <Card className={`p-6 border-caos-line bg-white caos-fade-in caos-delay-200 ${data.active_now > 0 ? "border-2 border-caos-terracotta" : ""}`}>
            <div className="flex items-center gap-2 text-caos-mute text-xs font-bold uppercase tracking-widest">
              <Heart className="w-3.5 h-3.5" /> Active calls
            </div>
            <p className="font-display text-4xl mt-2 text-caos-forest">{data.active_now}</p>
            <p className="text-caos-mute text-sm mt-1">
              {data.active_now === 0 ? "All clear." : "Staff are with them or on the way."}
            </p>
          </Card>
          <Card className="p-6 border-caos-line bg-white caos-fade-in caos-delay-300">
            <div className="flex items-center gap-2 text-caos-mute text-xs font-bold uppercase tracking-widest">
              <CheckCircle2 className="w-3.5 h-3.5" /> Resolved this week
            </div>
            <p className="font-display text-4xl mt-2 text-caos-forest">{data.resolved_last_7d}</p>
            <p className="text-caos-mute text-sm mt-1">All handled by staff.</p>
          </Card>
        </div>

        {/* Haiku */}
        {data.haiku && (
          <Card className="mt-10 p-8 border-caos-line bg-gradient-to-br from-white to-caos-ambient">
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-3">
              A small note from CAOS
            </p>
            <p className="font-display text-2xl md:text-3xl font-light text-caos-forest leading-relaxed whitespace-pre-line italic">
              {data.haiku.text}
            </p>
            <p className="text-caos-mute text-xs mt-4">
              Written {timeAgo(data.haiku.created_at)}
            </p>
          </Card>
        )}

        {/* Recent alerts */}
        <section className="mt-12">
          <h2 className="font-display text-2xl font-medium text-caos-forest mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5" /> Recent moments
          </h2>
          <div className="space-y-3">
            {data.recent_alerts.length === 0 && (
              <Card className="p-6 text-center border-caos-line">
                <p className="text-caos-mute">Nothing to note in the last 7 days.</p>
              </Card>
            )}
            {data.recent_alerts.map((a) => (
              <Card
                key={a.alert_id}
                className="p-4 border-caos-line bg-white"
                style={{ borderLeftWidth: 4, borderLeftColor: SEV_COLOR[a.severity] || "#4A7C59" }}
                data-testid={`family-alert-${a.alert_id}`}
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="uppercase tracking-wider text-xs">{a.severity}</Badge>
                  <Badge variant="outline" className="uppercase tracking-wider text-xs">{a.status}</Badge>
                  <span className="text-caos-mute text-xs">{timeAgo(a.created_at)}</span>
                </div>
                <p className="mt-2 text-caos-ink">
                  {a.status === "resolved"
                    ? <>Staff helped {data.resident.name} and closed the visit{a.outcome ? <> — <i>{a.outcome}</i></> : null}.</>
                    : a.status === "acknowledged"
                    ? <>Staff have acknowledged and are on their way to {data.resident.name}.</>
                    : <>A call was placed; staff are responding to {data.resident.name} now.</>}
                </p>
              </Card>
            ))}
          </div>
        </section>

        {/* Privacy note */}
        <Card className="mt-10 p-5 border-caos-line bg-caos-ambient/50">
          <div className="flex items-start gap-3">
            <Shield className="w-5 h-5 text-caos-forest mt-0.5" />
            <div className="text-sm text-caos-ink/80">
              <p className="font-semibold text-caos-forest mb-1">What you're seeing (and what you're not)</p>
              <p>
                This page shows call summaries — not medical detail, not companion chat content. Your notification
                preferences: {data.contact.notify_on.length > 0 ? data.contact.notify_on.join(", ") : "none"}.
                To change these, contact the facility.
              </p>
            </div>
          </div>
        </Card>

        <div className="mt-10 flex justify-end">
          <Button variant="outline" onClick={markRead} data-testid="mark-read-btn" className="border-2 rounded-full">
            I've checked in on {data.resident.name.split(" ")[0]}
          </Button>
        </div>

        <footer className="mt-14 text-center text-caos-mute text-xs">
          <p>© 2026 CAOS Care · This is a private family view. Please don't share this link.</p>
        </footer>
      </div>
    </div>
  );
}
