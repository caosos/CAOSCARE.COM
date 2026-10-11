import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { LogOut, RefreshCw } from "lucide-react";
import { MyTasksCard } from "./TasksTab";
import MaintenanceWorkspace from "./MaintenanceWorkspace";
import TransportationCalendar from "./TransportationCalendar";
import CommunityServicesWorkspace from "./CommunityServicesWorkspace";
import DepartmentQueue from "./DepartmentQueue";
import { SERVICES_DEPARTMENTS } from "../lib/communityServices";

// One shared operational workspace, rendered per the signed-in staff
// member's Department (User.department -> Department.slug). It reuses the
// existing StaffTask / resident-request bus - GET /tasks is already
// department-scoped server-side for a `staff` role by their User.department
// (routes/tasks.py::list_tasks), so this is that same data, shaped for the
// people who own it. No new task/department model. Care/Nursing and
// unassigned staff are routed to /staff (the resident-assistance board)
// instead of here - see lib/roleHome.js.

export default function DepartmentWorkspace() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [departments, setDepartments] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);   // Refresh re-mounts the shared queue

  const dept = user?.department || null;
  const deptLabel = useMemo(() => {
    const d = departments.find((x) => x.slug === dept);
    // GET /departments is admin-only, so department staff fall back to the slug.
    return d ? d.label : dept && dept.charAt(0).toUpperCase() + dept.slice(1);
  }, [departments, dept]);

  useEffect(() => {
    api.get("/departments/labels").then(({ data }) => setDepartments(data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-caos-bone">
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-y-2 px-4 sm:px-6 py-4">
          <Link to="/" className="text-xl">
            <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
            <span className="font-display font-light text-caos-forest">Care</span>
          </Link>
          <div className="flex items-center gap-3 overflow-x-auto max-w-full">
            {["owner", "admin"].includes(user?.role) && (
              <Link to="/admin"><Button variant="outline" className="border-2 h-10 rounded-full">Admin</Button></Link>
            )}
            <span className="text-sm text-caos-mute hidden md:block">
              {user?.name}{deptLabel ? ` · ${deptLabel}` : ""}
            </span>
            <Button variant="outline" onClick={async () => { await logout(); nav("/login"); }} className="border-2 h-10 rounded-full" data-testid="workspace-logout-btn">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <h1 className="font-display text-4xl font-light text-caos-forest">
            {deptLabel ? `${deptLabel} workspace` : "Workspace"}
          </h1>
          <Button variant="ghost" onClick={() => setReloadKey((k) => k + 1)} data-testid="workspace-refresh">
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </Button>
        </div>

        {!dept && (
          <Card className="border-caos-line p-8 text-center" data-testid="workspace-no-dept">
            <p className="font-display text-lg text-caos-forest">No department assigned yet.</p>
            <p className="text-caos-mute mt-1">
              Ask an administrator to set your department, or{" "}
              <Link to="/staff" className="underline">go to the resident-assistance board</Link>.
            </p>
          </Card>
        )}

        {/* Maintenance gets the full work-order workspace; housekeeping,
            kitchen and activities the community-services workspace; every
            other department the generic queue below. Same StaffTask data
            either way. */}
        {dept === "maintenance" && <MaintenanceWorkspace />}
        {SERVICES_DEPARTMENTS.includes(dept) && <CommunityServicesWorkspace department={dept} />}

        {/* Transportation works from the ride calendar: Departed / Ride
            completed update the ride and every rider's request together. */}
        {dept === "transportation" && (
          <div className="space-y-6">
            <TransportationCalendar />
            <MyTasksCard />
          </div>
        )}

        {dept && dept !== "maintenance" && dept !== "transportation" && !SERVICES_DEPARTMENTS.includes(dept) && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <section className="lg:col-span-2">
              {/* Therapy, Resident Programs and any other department work the same
                  shared queue nursing/maintenance/housekeeping use (claim, note,
                  plan the visit window, complete, cancel, reopen, history). */}
              <DepartmentQueue key={reloadKey} department={dept} title={`${deptLabel || "Department"} requests`} />
            </section>
            <section className="space-y-6">
              <MyTasksCard />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
