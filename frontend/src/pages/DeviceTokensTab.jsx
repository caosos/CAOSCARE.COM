import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Trash2, Plus, KeyRound, Copy, Shield, AlertCircle } from "lucide-react";
import { toast } from "sonner";

const SCOPE_LABELS = {
  "pendants.event": "Pendants (RF bridge)",
  "locations.ingest": "Location ingest",
  "wearables.event": "Wearables ingest",
};

export default function DeviceTokensTab() {
  const [tokens, setTokens] = useState([]);
  const [status, setStatus] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", scopes: ["pendants.event", "locations.ingest"] });
  const [showSecret, setShowSecret] = useState(null);

  const fetchAll = async () => {
    try {
      const [tRes, sRes] = await Promise.all([
        api.get("/device-tokens"),
        api.get("/device-tokens/status"),
      ]);
      setTokens(tRes.data);
      setStatus(sRes.data);
    } catch (err) {
      if (err?.response?.status === 403) toast.error("Admin access required");
    }
  };
  useEffect(() => { fetchAll(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (form.scopes.length === 0) { toast.error("Pick at least one scope"); return; }
    try {
      const { data } = await api.post("/device-tokens", form);
      setShowSecret(data);
      setForm({ name: "", scopes: ["pendants.event", "locations.ingest"] });
      setOpen(false);
      fetchAll();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const revoke = async (id) => {
    if (!window.confirm("Revoke this device token? Field devices using it will stop working immediately.")) return;
    await api.delete(`/device-tokens/${id}`);
    toast.success("Revoked");
    fetchAll();
  };

  const toggleScope = (scope) => {
    setForm({
      ...form,
      scopes: form.scopes.includes(scope) ? form.scopes.filter((s) => s !== scope) : [...form.scopes, scope],
    });
  };

  const copy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied");
  };

  return (
    <div className="space-y-6" data-testid="device-tokens-panel">
      {/* Enforcement status */}
      <Card className="border-caos-line p-5">
        <div className="flex items-start gap-3">
          <Shield className="w-5 h-5 text-caos-forest mt-0.5" />
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-display text-lg font-medium text-caos-forest">Field device authentication</h3>
              {status?.enforcement_required
                ? <Badge className="bg-caos-moss text-white uppercase tracking-wider text-xs font-bold">Enforced</Badge>
                : <Badge variant="outline" className="uppercase tracking-wider text-xs">Soft-enforced</Badge>}
            </div>
            <p className="text-caos-mute text-sm mt-2 max-w-3xl">
              Field hardware (Android bridge, location sensors, wearable gateways) can sign every request with
              HMAC-SHA256(shared_secret, request_body). Send <code className="bg-caos-ambient px-1 rounded text-xs">X-Device-Token</code> and
              <code className="bg-caos-ambient px-1 rounded text-xs"> X-Device-Signature</code> headers.
              Currently <b>{status?.enforcement_required ? "required" : "optional"}</b> —
              {status?.enforcement_required
                ? " unsigned requests are rejected."
                : " unsigned requests still work for backward compatibility. Set DEVICE_AUTH_REQUIRED=true in backend/.env to enforce."}
            </p>
            <p className="text-caos-mute text-sm mt-2">
              Active tokens: <b>{status?.active_tokens ?? 0}</b> · Revoked: {status?.revoked_tokens ?? 0}
            </p>
          </div>
        </div>
      </Card>

      {/* Tokens table */}
      <Card className="border-caos-line p-5">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-display text-lg font-medium text-caos-forest">Device tokens</h3>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-token-btn">
                <Plus className="w-4 h-4 mr-2" /> Create token
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle className="font-display">New device token</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-4">
                <div><Label>Name</Label><Input required data-testid="tok-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Hallway A tablet" /></div>
                <div>
                  <Label>Scopes</Label>
                  <div className="space-y-2 mt-2">
                    {Object.keys(SCOPE_LABELS).map((s) => (
                      <label key={s} className="flex items-center gap-2 cursor-pointer" data-testid={`tok-scope-${s.replace(".", "-")}`}>
                        <Checkbox checked={form.scopes.includes(s)} onCheckedChange={() => toggleScope(s)} />
                        <span className="text-sm"><code className="text-xs bg-caos-ambient px-1 rounded">{s}</code> — {SCOPE_LABELS[s]}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="tok-save">Create</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Table>
          <TableHeader>
            <TableRow><TableHead>Name</TableHead><TableHead>Token id</TableHead><TableHead>Scopes</TableHead><TableHead>Last used</TableHead><TableHead>Status</TableHead><TableHead></TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {tokens.map((t) => (
              <TableRow key={t.token_id} data-testid={`tok-row-${t.token_id}`}>
                <TableCell className="font-medium">{t.name}</TableCell>
                <TableCell className="font-mono text-xs">{t.token_id}</TableCell>
                <TableCell><div className="flex flex-wrap gap-1">{(t.scopes || []).map((s) => <Badge key={s} variant="outline" className="text-xs">{s}</Badge>)}</div></TableCell>
                <TableCell className="text-caos-mute text-xs">{t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "Never"}</TableCell>
                <TableCell>
                  {t.revoked ? <Badge className="bg-caos-terracotta text-white uppercase text-xs">Revoked</Badge> : <Badge className="bg-caos-moss text-white uppercase text-xs">Active</Badge>}
                </TableCell>
                <TableCell>
                  {!t.revoked && (
                    <Button variant="ghost" size="sm" onClick={() => revoke(t.token_id)} data-testid={`del-tok-${t.token_id}`}>
                      <Trash2 className="w-4 h-4 text-caos-terracotta" />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {tokens.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-caos-mute py-6">No device tokens yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Secret reveal dialog */}
      <Dialog open={!!showSecret} onOpenChange={(o) => { if (!o) setShowSecret(null); }}>
        <DialogContent className="max-w-xl" data-testid="secret-reveal-dialog">
          <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><KeyRound className="w-5 h-5 text-caos-amber" /> Save this shared secret now</DialogTitle></DialogHeader>
          {showSecret && (
            <div className="space-y-4">
              <div className="bg-caos-terracotta/10 border border-caos-terracotta rounded-xl p-3 flex items-start gap-2 text-sm">
                <AlertCircle className="w-4 h-4 text-caos-terracotta mt-0.5 shrink-0" />
                <p className="text-caos-terracotta-dark">
                  This secret is shown <b>only once</b>. Copy it to the device now. We store only a hash — we cannot show it to you again.
                </p>
              </div>
              <div>
                <Label>Token ID</Label>
                <div className="flex gap-2 mt-1">
                  <Input readOnly value={showSecret.token_id} className="font-mono text-xs" />
                  <Button variant="outline" onClick={() => copy(showSecret.token_id)}><Copy className="w-4 h-4" /></Button>
                </div>
              </div>
              <div>
                <Label>Shared secret</Label>
                <div className="flex gap-2 mt-1">
                  <Input readOnly value={showSecret.shared_secret} className="font-mono text-xs" data-testid="secret-value" />
                  <Button variant="outline" onClick={() => copy(showSecret.shared_secret)} data-testid="copy-secret-btn"><Copy className="w-4 h-4" /></Button>
                </div>
              </div>
              <div>
                <Label>Example (Python)</Label>
                <pre className="bg-caos-ambient rounded-lg p-3 text-xs mt-1 overflow-x-auto"><code>{showSecret.example_python}</code></pre>
              </div>
              <DialogFooter>
                <Button onClick={() => setShowSecret(null)} className="bg-caos-forest">I've saved it</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
