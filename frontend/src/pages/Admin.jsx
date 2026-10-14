import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { toast } from "sonner";
import RFPairingTab from "./RFPairingTab";
import ClinicianTab from "./ClinicianTab";
import HardwareReceiptsTab from "./HardwareReceiptsTab";
import FacilitiesTab from "./FacilitiesTab";
import FacilitySetupBanner from "./FacilitySetupBanner";
import EscalationTab from "./EscalationTab";
import Roadmap from "./Roadmap";
import Insights from "./Insights";
import FamilyTab from "./FamilyTab";
import CommunicationsTab from "./CommunicationsTab";
import PhoneCallsPanel from "./PhoneCallsPanel";
import WearablesTab from "./WearablesTab";
import DeviceTokensTab from "./DeviceTokensTab";
import DevicesTab from "./DevicesTab";
import TasksTab from "./TasksTab";
import RequestsBoard from "./RequestsBoard";
import MedicationsTab from "./MedicationsTab";
import FloorPlanTab from "./FloorPlanTab";
import AuditTab from "./AuditTab";
import ScheduleTab from "./ScheduleTab";
import MenuTab from "./MenuTab";
import TransportationTab from "./TransportationTab";
import TransportationCalendar from "./TransportationCalendar";
import TransportResourcesTab from "./TransportResourcesTab";
import TransportLog from "./TransportLog";
import DepartmentsTab from "./DepartmentsTab";
import ResidentsTab from "./ResidentsTab";
import StaffTab from "./StaffTab";
import KiosksTab from "./KiosksTab";
import ZonesTab from "./ZonesTab";
import { tabGroups, resolveTab } from "../lib/adminTabGroups";
import { fetchFacilitySnapshot } from "../lib/facilityLoad";
import OperationsOverview from "./OperationsOverview";
import RoutingExceptionsBoard from "./RoutingExceptionsBoard";
import LiveOperations from "./LiveOperations";
import MaintenanceWorkspace from "./MaintenanceWorkspace";
import DepartmentQueue from "./DepartmentQueue";
import QueueWithUpcoming from "../components/QueueWithUpcoming";
import ActivityLog from "./ActivityLog";
import ReportsTab from "./ReportsTab";
import AlertsBoard from "./AlertsBoard";
import AriaSpotlight from "../components/admin/AriaSpotlight";
import WorkspaceShell from "../components/workspace/WorkspaceShell";
import { NAV_SECTIONS } from "../lib/workspaceNav";

export default function Admin() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();

  const [residents, setResidents] = useState([]);
  const [staff, setStaff] = useState([]);
  const [kiosks, setKiosks] = useState([]);
  const [zones, setZones] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [facilityLoadState, setFacilityLoadState] = useState("loading");
  const [autoOpenFacilityDialog, setAutoOpenFacilityDialog] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [focusResidentId, setFocusResidentId] = useState(null);

  const groups = useMemo(() => tabGroups(residents, staff, kiosks, zones, user), [residents, staff, kiosks, zones, user]);

  // Deep links: /admin?tab=<value>&resident=<id> (workspace sidebar, staff
  // dashboard cards, Admin Aria, notifications). The open tab stays in the
  // URL so reload, shared links and Back return to the same section;
  // `resident` is consumed once.
  useEffect(() => {
    const t = resolveTab(sp.get("tab"), groups);
    const rid = sp.get("resident");
    if (t && t !== activeTab) setActiveTab(t);
    if (rid) {
      setFocusResidentId(rid);
      if (!t) setActiveTab("residents");
      setSp((p) => { const n = new URLSearchParams(p); n.delete("resident"); return n; }, { replace: true });
    }
  }, [sp, groups]); // eslint-disable-line react-hooks/exhaustive-deps
  const urlRead = useRef(false);   // write the tab back only after the incoming link has been applied
  useEffect(() => {
    if (!urlRead.current) { urlRead.current = true; if (resolveTab(sp.get("tab"), groups)) return; }
    if (sp.get("tab") !== activeTab && !(sp.get("tab") && resolveTab(sp.get("tab"), groups) === activeTab)) {
      setSp((p) => { const n = new URLSearchParams(p); n.set("tab", activeTab); return n; }, { replace: true });
    }
  }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadFacilities = useCallback(async () => {
    setFacilityLoadState("loading");
    const snapshot = await fetchFacilitySnapshot(api);
    if (snapshot.facilities) setFacilities(snapshot.facilities);
    // An unavailable read is unknown, not proof that no community exists.
    // Keep any last-known facilities and let the banner offer a truthful retry.
    setFacilityLoadState(snapshot.loadState);
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [r, s, k, z] = await Promise.all([
        api.get("/residents"), api.get("/staff"), api.get("/kiosks"), api.get("/zones"),
      ]);
      setResidents(r.data); setStaff(s.data); setKiosks(k.data); setZones(z.data);
    } catch (e) {
      if (e?.response?.status === 403) { toast.error("Admin access required"); nav("/staff"); }
    }
    await loadFacilities();
  }, [loadFacilities, nav]);

  const goSetUpCommunity = () => { setActiveTab("facilities"); setAutoOpenFacilityDialog(true); };
  // Stable identity (empty deps - only calls api.get/setFacilities) so
  // FacilitiesTab's own mount-effect dependency on this prop doesn't
  // refire on every Admin re-render.
  const refreshFacilities = loadFacilities;

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // In the shared application shell (owner direction 2026-10-14): the sidebar
  // replaces the old header and group pills; the section's own tabs stay as
  // a tab bar, so every existing tab and its content is unchanged.
  const section = NAV_SECTIONS.find((s) => s.items.some((i) => i.tab === activeTab));
  const sectionTabs = (section?.items || []).filter((i) => i.tab && groups.some((g) => g.tabs.some((t) => t.value === i.tab)));
  const tabLabel = groups.flatMap((g) => g.tabs).find((t) => t.value === activeTab)?.label || activeTab;

  return (
    <WorkspaceShell crumbs={section && section.id !== "dashboard" ? [{ label: section.label }, { label: tabLabel }] : [{ label: tabLabel }]}
                    activeSection={section?.id} ariaSection={activeTab} onAriaNavigate={setActiveTab}>
      <div className="ws-legacy mt-1" data-testid="admin-in-shell">
        <h1 className="text-[28px] font-bold leading-tight tracking-tight sm:text-[36px]">{tabLabel}</h1>

        <FacilitySetupBanner facilities={facilities} loadState={facilityLoadState}
          isOwner={user?.role === "owner"} onSetup={goSetUpCommunity} onRetry={loadFacilities} />

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mt-4 h-auto flex-wrap justify-start gap-1 rounded-xl border border-[#E5E7EB] bg-white p-1">
            {sectionTabs.map((t) => (
              <TabsTrigger key={t.tab} value={t.tab} data-testid={`tab-${t.tab}`}
                className="rounded-lg px-3 py-1.5 text-[14px] data-[state=active]:bg-[#2F80ED] data-[state=active]:text-white">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="overview" className="mt-6"><OperationsOverview onNavigate={setActiveTab} /></TabsContent>
          <TabsContent value="routing-exceptions" className="mt-6"><RoutingExceptionsBoard /></TabsContent>
          <TabsContent value="live-operations" className="mt-6"><LiveOperations /></TabsContent>
          <TabsContent value="alerts" className="mt-6"><AlertsBoard /></TabsContent>
          <TabsContent value="nursing" className="mt-6"><DepartmentQueue department="nursing" title="Nursing requests" adminMode /></TabsContent>
          <TabsContent value="maintenance" className="mt-6"><MaintenanceWorkspace adminMode /></TabsContent>
          <TabsContent value="housekeeping" className="mt-6"><QueueWithUpcoming department="housekeeping" title="Housekeeping requests" adminMode /></TabsContent>
          <TabsContent value="therapy" className="mt-6"><QueueWithUpcoming department="therapy" title="Therapy appointments" adminMode /></TabsContent>
          <TabsContent value="kitchen" className="mt-6"><DepartmentQueue department="kitchen" title="Kitchen requests" adminMode /></TabsContent>
          <TabsContent value="activities" className="mt-6 space-y-8">
            <DepartmentQueue department="activities" title="Activities requests" adminMode />
            <ScheduleTab />
          </TabsContent>
          <TabsContent value="residents" className="mt-6">
            <ResidentsTab residents={residents} kiosks={kiosks} onChange={fetchAll}
              focusResidentId={focusResidentId} onFocusHandled={() => setFocusResidentId(null)} />
          </TabsContent>
          <TabsContent value="clinician" className="mt-6"><ClinicianTab residents={residents} /></TabsContent>
          <TabsContent value="rf" className="mt-6"><RFPairingTab /></TabsContent>
          <TabsContent value="wearables" className="mt-6"><WearablesTab residents={residents} /></TabsContent>
          <TabsContent value="devices" className="mt-6"><DevicesTab residents={residents} /></TabsContent>
          <TabsContent value="requests" className="mt-6"><RequestsBoard /></TabsContent>
          <TabsContent value="tasks" className="mt-6"><TasksTab residents={residents} staff={staff} /></TabsContent>
          <TabsContent value="schedule" className="mt-6"><ScheduleTab /></TabsContent>
          <TabsContent value="menu" className="mt-6"><MenuTab /></TabsContent>
          <TabsContent value="transportation" className="mt-6"><TransportationTab /></TabsContent>
          <TabsContent value="transport-calendar" className="mt-6"><TransportationCalendar /></TabsContent>
          <TabsContent value="transport-log" className="mt-6"><TransportLog /></TabsContent>
          <TabsContent value="transport-resources" className="mt-6"><TransportResourcesTab /></TabsContent>
          <TabsContent value="departments" className="mt-6"><DepartmentsTab /></TabsContent>
          <TabsContent value="meds" className="mt-6"><MedicationsTab residents={residents} /></TabsContent>
          <TabsContent value="map" className="mt-6"><FloorPlanTab /></TabsContent>
          <TabsContent value="staff" className="mt-6"><StaffTab staff={staff} onChange={fetchAll} /></TabsContent>
          <TabsContent value="kiosks" className="mt-6"><KiosksTab kiosks={kiosks} zones={zones} onChange={fetchAll} /></TabsContent>
          <TabsContent value="zones" className="mt-6"><ZonesTab zones={zones} onChange={fetchAll} /></TabsContent>
          <TabsContent value="family" className="mt-6"><FamilyTab residents={residents} /></TabsContent>
          <TabsContent value="communications" className="mt-6"><CommunicationsTab /></TabsContent>
          <TabsContent value="phones" className="mt-6"><PhoneCallsPanel /></TabsContent>
          <TabsContent value="tokens" className="mt-6"><DeviceTokensTab /></TabsContent>
          <TabsContent value="insights" className="mt-6"><Insights /></TabsContent>
          <TabsContent value="audit" className="mt-6"><AuditTab /></TabsContent>
          <TabsContent value="hardware" className="mt-6"><HardwareReceiptsTab /></TabsContent>
          <TabsContent value="escalation" className="mt-6"><EscalationTab /></TabsContent>
          {user?.role === "owner" && (
            <TabsContent value="facilities" className="mt-6">
              <FacilitiesTab autoOpenAdd={autoOpenFacilityDialog} onAutoOpenHandled={() => setAutoOpenFacilityDialog(false)} onChange={refreshFacilities} />
            </TabsContent>
          )}
          <TabsContent value="reports" className="mt-6"><ReportsTab /></TabsContent>
          <TabsContent value="activity" className="mt-6"><ActivityLog onNavigate={setActiveTab} /></TabsContent>
          <TabsContent value="roadmap" className="mt-6"><Roadmap /></TabsContent>
        </Tabs>
      </div>
      <AriaSpotlight />
    </WorkspaceShell>
  );
}
