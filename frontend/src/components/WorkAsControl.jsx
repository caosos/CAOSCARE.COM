import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { clearWorkContext, readWorkContext, saveWorkContext, useWorkContext, workContextToken } from "../lib/workContext";
import { Button } from "./ui/button";
import { toast } from "sonner";

export default function WorkAsControl({ onEntered, onExited }) {
  const active = useWorkContext();
  const [departments, setDepartments] = useState([]);
  const [department, setDepartment] = useState("");
  const [role, setRole] = useState("staff");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/work-context/options")
      .then(({ data }) => {
        setDepartments(data.departments || []);
        setDepartment((current) => current || data.departments?.[0]?.slug || "");
      })
      .catch(() => {});
    if (readWorkContext()) {
      api.get("/work-context/current")
        .then(({ data }) => saveWorkContext(workContextToken(), data))
        .catch(() => clearWorkContext());
    }
  }, []);

  const label = useMemo(
    () => departments.find((d) => d.slug === active?.acting_department)?.label || active?.acting_department,
    [active, departments]
  );

  const enter = async () => {
    if (!department) return;
    setBusy(true);
    try {
      const { data } = await api.post("/work-context", { acting_role: role, acting_department: department });
      saveWorkContext(data.token, data.context);
      toast.success(`Working as ${role === "front_desk" ? "Front Desk" : labelFor(departments, department)}`);
      onEntered?.(data.context);
    } catch (err) {
      toast.error(err?.response?.data?.detail?.message || "Could not enter this department");
    } finally {
      setBusy(false);
    }
  };

  const exit = () => {
    clearWorkContext();
    toast.success("Returned to your admin role");
    onExited?.();
  };

  if (active) {
    return (
      <div className="flex items-center gap-2" data-testid="work-as-active">
        <span className="text-sm font-semibold text-caos-forest">
          Working as {active.acting_role === "front_desk" ? "Front Desk" : label}
        </span>
        <span className="text-xs text-caos-mute">
          until {new Date(active.expires_at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
        </span>
        <Button variant="outline" className="h-9 rounded-full" onClick={exit} data-testid="work-as-exit">
          Exit Work-as
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2" data-testid="work-as-picker">
      <select value={department} aria-label="Work-as department" onChange={(event) => {
        const value = event.target.value;
        setDepartment(value);
        if (role === "front_desk" && value !== "administration") setRole("staff");
      }} className="w-44 h-9 rounded-md border border-caos-line bg-white px-3 text-sm">
        <option value="" disabled>Department</option>
        {departments.map((d) => <option key={d.slug} value={d.slug}>{d.label}</option>)}
      </select>
      <select value={role} aria-label="Work-as role" onChange={(event) => setRole(event.target.value)}
        className="w-32 h-9 rounded-md border border-caos-line bg-white px-3 text-sm">
        <option value="staff">Staff</option>
        {department === "administration" && <option value="front_desk">Front Desk</option>}
      </select>
      <Button className="h-9 rounded-full" onClick={enter} disabled={busy || !department} data-testid="work-as-enter">
        {busy ? "Entering…" : "Work as"}
      </Button>
    </div>
  );
}

function labelFor(departments, slug) {
  return departments.find((d) => d.slug === slug)?.label || slug;
}
