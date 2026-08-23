import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
import { Building2, Plus, Phone, Mail, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

// Multi-tenant facilities. Owner can create/edit; admins read-only.

// autoOpenAdd: set by Admin.jsx's onboarding banner ("Set up your community")
// so the create dialog opens immediately instead of landing on a screen
// that still requires finding the "New facility" button.
export default function FacilitiesTab({ autoOpenAdd = false, onAutoOpenHandled, onChange }) {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const autoOpenedRef = useRef(false);

  const refresh = async () => {
    try {
      const { data } = await api.get("/facilities");
      setItems(data);
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed to load"); }
    finally { setLoading(false); onChange && onChange(); }
  };
  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (autoOpenAdd && !autoOpenedRef.current && user?.role === "owner") {
      autoOpenedRef.current = true;
      setAddOpen(true);
      onAutoOpenHandled && onAutoOpenHandled();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpenAdd, user]);

  return (
    <div className="space-y-6" data-testid="facilities-tab">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display text-3xl text-caos-forest">Facilities</h2>
          <p className="text-caos-mute text-sm mt-1">
            Each facility is its own tenant. Residents, staff, and devices belong to one facility.
          </p>
        </div>
        {user?.role === "owner" && (
          <Button onClick={() => setAddOpen(true)} data-testid="fac-add-btn" className="bg-caos-terracotta hover:bg-caos-terracotta-dark rounded-full">
            <Plus className="w-4 h-4 mr-2" /> New facility
          </Button>
        )}
      </div>

      {loading && <div className="py-12 text-center"><Loader2 className="w-8 h-8 animate-spin text-caos-forest mx-auto" /></div>}

      {!loading && items.length === 0 && (
        <Card className="p-8 text-center border-caos-line">
          <Building2 className="w-10 h-10 text-caos-mute mx-auto" />
          <p className="text-caos-mute italic mt-3">No facilities yet. Add the first one to start scoping data.</p>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {items.map((f) => (
          <FacilityCard key={f.facility_id} facility={f} onChange={refresh} canEdit={user?.role === "owner"} />
        ))}
      </div>

      <AddDialog open={addOpen} onClose={() => { setAddOpen(false); refresh(); }} />
    </div>
  );
}

function FacilityCard({ facility, onChange, canEdit }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(facility);
  useEffect(() => setDraft(facility), [facility]);

  const save = async () => {
    try {
      await api.patch(`/facilities/${facility.facility_id}`, draft);
      toast.success("Saved");
      setEditing(false); onChange();
    } catch (err) { toast.error(err?.response?.data?.detail || "Save failed"); }
  };

  return (
    <Card className="p-5 border-caos-line" data-testid={`fac-card-${facility.facility_id}`}>
      <div className="flex items-start justify-between mb-2">
        <Building2 className="w-5 h-5 text-caos-forest" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-widest text-caos-mute">{facility.plan}</span>
          {canEdit && <Switch checked={facility.is_active} onCheckedChange={(v) => api.patch(`/facilities/${facility.facility_id}`, { is_active: v }).then(onChange)} data-testid={`fac-toggle-${facility.facility_id}`} />}
        </div>
      </div>
      {editing ? (
        <div className="space-y-2">
          <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Name" />
          <Input value={draft.address || ""} onChange={(e) => setDraft({ ...draft, address: e.target.value })} placeholder="Address" />
          <Input value={draft.timezone || ""} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} placeholder="Timezone (e.g. America/New_York)" />
          <Input value={draft.contact_email || ""} onChange={(e) => setDraft({ ...draft, contact_email: e.target.value })} placeholder="Contact email" />
          <Input value={draft.phone || ""} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} placeholder="Phone" />
          <Input value={draft.on_call_phone || ""} onChange={(e) => setDraft({ ...draft, on_call_phone: e.target.value })} placeholder="On-call phone (escalation)" />
          <div className="flex gap-2">
            <Button onClick={save} className="bg-caos-forest" size="sm">Save</Button>
            <Button onClick={() => { setEditing(false); setDraft(facility); }} variant="outline" size="sm">Cancel</Button>
          </div>
        </div>
      ) : (
        <>
          <h3 className="font-display text-2xl text-caos-forest">{facility.name}</h3>
          <p className="text-xs text-caos-mute font-mono mt-1">{facility.facility_id}</p>
          <div className="mt-3 space-y-1 text-sm text-caos-ink/80">
            {facility.address && <p className="text-caos-ink/80">{facility.address}</p>}
            <p className="text-caos-mute text-xs">{facility.timezone}</p>
            {facility.contact_email && <p className="flex items-center gap-2"><Mail className="w-3.5 h-3.5 text-caos-mute" /> {facility.contact_email}</p>}
            {facility.phone && <p className="flex items-center gap-2"><Phone className="w-3.5 h-3.5 text-caos-mute" /> {facility.phone}</p>}
            {facility.on_call_phone && <p className="flex items-center gap-2 text-caos-terracotta"><Phone className="w-3.5 h-3.5" /> on-call: {facility.on_call_phone}</p>}
          </div>
          {canEdit && (
            <Button onClick={() => setEditing(true)} variant="outline" size="sm" className="mt-3" data-testid={`fac-edit-${facility.facility_id}`}>Edit</Button>
          )}
        </>
      )}
    </Card>
  );
}

function AddDialog({ open, onClose }) {
  const [draft, setDraft] = useState({ name: "", address: "", contact_email: "", phone: "", on_call_phone: "", plan: "pilot", timezone: "America/New_York" });
  if (!open) return null;
  const submit = async () => {
    if (!draft.name.trim()) { toast.error("Name required"); return; }
    try {
      await api.post("/facilities", draft);
      toast.success("Facility created");
      onClose();
    } catch (err) { toast.error(err?.response?.data?.detail || "Create failed"); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose} data-testid="fac-add-dialog">
      <Card className="p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-display text-2xl text-caos-forest mb-3">New facility</h3>
        <div className="space-y-2">
          <Input placeholder="Name (e.g. Sunrise Senior Living — Boston)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} data-testid="fac-add-name" />
          <Input placeholder="Address" value={draft.address} onChange={(e) => setDraft({ ...draft, address: e.target.value })} data-testid="fac-add-address" />
          <Input placeholder="Timezone (e.g. America/New_York)" value={draft.timezone} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} data-testid="fac-add-timezone" />
          <Input placeholder="Contact email" value={draft.contact_email} onChange={(e) => setDraft({ ...draft, contact_email: e.target.value })} data-testid="fac-add-email" />
          <Input placeholder="Main phone" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
          <Input placeholder="On-call phone (for escalation)" value={draft.on_call_phone} onChange={(e) => setDraft({ ...draft, on_call_phone: e.target.value })} />
        </div>
        <div className="flex gap-2 justify-end mt-4">
          <Button onClick={onClose} variant="outline">Cancel</Button>
          <Button onClick={submit} className="bg-caos-forest" data-testid="fac-add-submit">Create</Button>
        </div>
      </Card>
    </div>
  );
}
