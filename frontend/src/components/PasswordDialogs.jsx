import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "./ui/dialog";
import { KeyRound } from "lucide-react";
import { toast } from "sonner";

export function MyPasswordDialog() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      toast.success("Password changed");
      setOpen(false);
      setCurrent("");
      setNext("");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="border-2 h-10 rounded-full" data-testid="my-password-btn">
          <KeyRound className="w-4 h-4 mr-2" /> Password
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader><DialogTitle className="font-display">Change my password</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div><Label>Current password</Label><Input required type="password" data-testid="my-pw-current" value={current} onChange={(e) => setCurrent(e.target.value)} /></div>
          <div><Label>New password</Label><Input required type="password" minLength={8} data-testid="my-pw-new" value={next} onChange={(e) => setNext(e.target.value)} /></div>
          <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="my-pw-save">Save</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function SetPasswordDialog({ userId, name }) {
  const [open, setOpen] = useState(false);
  const [next, setNext] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/staff/${userId}/password`, { new_password: next });
      toast.success(`Password set for ${name}`);
      setOpen(false);
      setNext("");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" data-testid={`set-pw-${userId}`}>
          <KeyRound className="w-4 h-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader><DialogTitle className="font-display">Set password for {name}</DialogTitle></DialogHeader>
        <p className="text-caos-mute text-sm">No current password needed — this is an admin override.</p>
        <form onSubmit={submit} className="space-y-3">
          <div><Label>New password</Label><Input required type="password" minLength={8} data-testid="set-pw-new" value={next} onChange={(e) => setNext(e.target.value)} /></div>
          <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="set-pw-save">Save</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
