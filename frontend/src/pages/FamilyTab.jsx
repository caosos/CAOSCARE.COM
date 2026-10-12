import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Trash2, Plus, Copy, Sparkles, Pencil } from "lucide-react";
import FamilyContactForm from "../components/FamilyContactForm";
import { toast } from "sonner";

export default function FamilyTab({ residents }) {
  const [contacts, setContacts] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const fetchAll = async () => {
    try {
      const cRes = await api.get("/family-contacts");
      setContacts(cRes.data);
    } catch {}
  };
  useEffect(() => { fetchAll(); }, []);

  const remove = async (id) => {
    if (!window.confirm("Remove this contact?")) return;
    await api.delete(`/family-contacts/${id}`);
    toast.success("Removed");
    fetchAll();
  };

  const setCalls = async (id, allow) => {
    try {
      await api.patch(`/family-contacts/${id}/calls`, { allow_calls: allow });
      toast.success(allow ? "Resident can call this contact" : "Calling turned off");
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };


  return (
    <div className="space-y-6" data-testid="family-panel">
      <p className="text-caos-mute text-sm">
        Family notifications are delivered through the providers on the Communications tab, where every
        attempt and its delivery status is listed.
      </p>

      {/* Family contacts */}
      <Card className="border-caos-line p-5">
        <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
          <h3 className="font-display text-lg font-medium text-caos-forest">Family contacts</h3>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              className="border-2 rounded-full"
              data-testid="generate-haikus-btn"
              onClick={async () => {
                try {
                  const { data } = await api.post("/haiku/generate-today");
                  toast.success(`Tonight's haikus: ${data.created} created, ${data.skipped} already done`);
                } catch (err) {
                  toast.error(err?.response?.data?.detail || "Could not generate haikus");
                }
              }}
            >
              <Sparkles className="w-4 h-4 mr-2" /> Generate tonight's haikus
            </Button>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" onClick={() => setOpen(true)} data-testid="add-family-btn">
              <Plus className="w-4 h-4 mr-2" /> Add family contact
            </Button>
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Contact</TableHead><TableHead>Resident</TableHead><TableHead>Phone</TableHead><TableHead>Email</TableHead><TableHead>Notify on</TableHead><TableHead>Resident may call</TableHead><TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((c) => {
              const resident = (residents || []).find((r) => r.resident_id === c.resident_id);
              return (
                <TableRow key={c.contact_id} data-testid={`fam-row-${c.contact_id}`}>
                  <TableCell>
                    <span className="font-medium">{c.name}</span>
                    {c.relationship && <span className="text-caos-mute text-xs block">{c.relationship}</span>}
                  </TableCell>
                  <TableCell>{resident ? `${resident.name} · ${resident.room}` : c.resident_id}</TableCell>
                  <TableCell className="font-mono text-xs">{c.phone || "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{c.email || "—"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {c.notify_on.map((k) => <Badge key={k} variant="outline" className="text-xs">{k}</Badge>)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Checkbox
                      checked={!!c.allow_calls}
                      disabled={!c.phone}
                      onCheckedChange={(v) => setCalls(c.contact_id, !!v)}
                      aria-label={`Allow ${c.name} to be called by the resident`}
                      data-testid={`fam-calls-${c.contact_id}`}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {c.portal_token && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Copy family portal link"
                          onClick={() => {
                            const url = `${window.location.origin}/family/${c.portal_token}`;
                            navigator.clipboard.writeText(url);
                            toast.success("Portal link copied");
                          }}
                          data-testid={`copy-portal-${c.contact_id}`}
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" title="Edit contact" onClick={() => setEditing(c)} data-testid={`edit-fam-${c.contact_id}`}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(c.contact_id)} data-testid={`del-fam-${c.contact_id}`}>
                        <Trash2 className="w-4 h-4 text-caos-terracotta" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
            {contacts.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center text-caos-mute py-6">No family contacts yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
      <FamilyContactForm open={open} onOpenChange={setOpen} residents={residents} onSaved={fetchAll} />
      <FamilyContactForm open={!!editing} onOpenChange={(o) => { if (!o) setEditing(null); }} residents={residents} contact={editing} onSaved={fetchAll} />
    </div>
  );
}
