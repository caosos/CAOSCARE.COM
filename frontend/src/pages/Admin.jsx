import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { LogOut, Activity, Sparkles } from "lucide-react";
import { MyPasswordDialog } from "../components/PasswordDialogs";
import { toast } from "sonner";
import PendantsTab from "./PendantsTab";
import RFPairingTab from "./RFPairingTab";
import ClinicianTab from "./ClinicianTab";
import HardwareReceiptsTab from "./HardwareReceiptsTab";
import FacilitiesTab from "./FacilitiesTab";
import FacilitySetupBanner from "./FacilitySetupBanner";
import EscalationTab from "./EscalationTab";
import Roadmap from "./Roadmap";
import Insights from "./Insights";
import FamilyTab from "./FamilyTab";
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
import DepartmentsTab from "./DepartmentsTab";
import ResidentsTab from "./ResidentsTab";
import StaffTab from "./StaffTab";
import KiosksTab from "./KiosksTab";
import ZonesTab from "./ZonesTab";
import { tabGroups } from "../lib/adminTabGroups";

export default function Admin() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const [residents, setResidents] = useState([]);
  const [staff, setStaff] = useState([]);
  const [kiosks, setKiosks] = useState([]);
  const [zones, setZones] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [facilitiesLoaded, setFacilitiesLoaded] = useState(false);
  const [autoOpenFacilityDialog, setAutoOpenFacilityDialog] = useState(false);
  const [activeTab, setActiveTab] = useState("residents");
  const activeGroupId = tabGroups(residents, staff, kiosks, zones, user)
    .find((g) => g.tabs.some((t) => t.value === activeTab))?.id;

  const fetchAll = async () => {
    try {
      const [r, s, k, z] = await Promise.all([
        api.get("/residents"),
        api.get("/staff"),
        api.get("/kiosks"),
        api.get("/zones"),
      ]);
      setResidents(r.data);
      setStaff(s.data);
      setKiosks(k.data);
      setZones(z.data);
    } catch (e) {
      if (e?.response?.status === 403) {
        toast.error("Admin access required");
        nav("/staff");
      }
    }
    // Facilities read is separate: any admin/owner can see the setup
    // banner, but a fetch failure here (e.g. non-owner edge case) must
    // never block the rest of the dashboard from loading.
    try {
      const f = await api.get("/facilities");
      setFacilities(f.data);
    } catch { /* banner just won't render; rest of Admin still works */ }
    finally { setFacilitiesLoaded(true); }
  };

  const goSetUpCommunity = () => {
    setActiveTab("facilities");
    setAutoOpenFacilityDialog(true);
  };

  // FacilitiesTab manages its own list for the tab itself; this keeps the
  // top-level banner state (rendered outside that tab) in sync whenever a
  // facility is created/edited there, so the banner disappears immediately
  // after setup instead of waiting for a full page reload.
  const refreshFacilities = async () => {
    try {
      const f = await api.get("/facilities");
      setFacilities(f.data);
    } catch { /* keep prior state */ }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  return (
    <div className="min-h-screen bg-caos-bone">
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-xl" data-testid="admin-home-link">
              <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
              <span className="font-display font-light text-caos-forest">Care</span>
            </Link>
            <span className="text-caos-mute text-sm">
              · {user?.role === "owner" ? "Owner" : "Admin"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            {user?.role === "owner" && (
              <Link to="/admin/blueprint" data-testid="admin-blueprint-link">
                <Button variant="outline" className="border-2 h-10 rounded-full border-caos-terracotta text-caos-terracotta hover:bg-caos-terracotta hover:text-white">
                  <Sparkles className="w-4 h-4 mr-2" /> Blueprint
                </Button>
              </Link>
            )}
            <Link to="/admin/help" data-testid="admin-help-link">
              <Button variant="outline" className="border-2 h-10 rounded-full">
                Tutorials
              </Button>
            </Link>
            <Link to="/staff" data-testid="admin-staff-link">
              <Button variant="outline" className="border-2 h-10 rounded-full">
                <Activity className="w-4 h-4 mr-2" /> Dashboard
              </Button>
            </Link>
            <span className="text-sm text-caos-mute hidden md:block">{user?.name}</span>
            <MyPasswordDialog />
            <Button
              variant="outline"
              onClick={async () => { await logout(); nav("/login"); }}
              className="border-2 h-10 rounded-full"
              data-testid="admin-logout-btn"
            >
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <h1 className="font-display text-4xl font-light text-caos-forest mb-6">Community administration</h1>

        <FacilitySetupBanner
          facilities={facilities}
          loaded={facilitiesLoaded}
          isOwner={user?.role === "owner"}
          onSetup={goSetUpCommunity}
        />

        <div className="flex flex-wrap gap-2 mb-4" data-testid="admin-group-nav">
          {tabGroups(residents, staff, kiosks, zones, user).map((g) => (
            <button
              key={g.id}
              onClick={() => setActiveTab(g.tabs[0].value)}
              data-testid={`group-${g.id}`}
              className={`px-4 py-2 rounded-full text-sm font-semibold uppercase tracking-wider transition-colors ${
                activeGroupId === g.id
                  ? "bg-caos-forest text-white"
                  : "bg-white border border-caos-line text-caos-mute hover:border-caos-forest"
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="flex-wrap h-auto">
            {tabGroups(residents, staff, kiosks, zones, user)
              .find((g) => g.id === activeGroupId)
              ?.tabs.map((t) => (
                <TabsTrigger key={t.value} value={t.value} data-testid={`tab-${t.value}`}>{t.label}</TabsTrigger>
              ))}
          </TabsList>

          <TabsContent value="residents" className="mt-6">
            <ResidentsTab residents={residents} kiosks={kiosks} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="clinician" className="mt-6">
            <ClinicianTab residents={residents} />
          </TabsContent>
          <TabsContent value="pendants" className="mt-6">
            <PendantsTab residents={residents} />
          </TabsContent>
          <TabsContent value="rf" className="mt-6">
            <RFPairingTab />
          </TabsContent>
          <TabsContent value="wearables" className="mt-6">
            <WearablesTab residents={residents} />
          </TabsContent>
          <TabsContent value="devices" className="mt-6">
            <DevicesTab residents={residents} />
          </TabsContent>
          <TabsContent value="requests" className="mt-6">
            <RequestsBoard />
          </TabsContent>
          <TabsContent value="tasks" className="mt-6">
            <TasksTab residents={residents} staff={staff} />
          </TabsContent>
          <TabsContent value="schedule" className="mt-6">
            <ScheduleTab />
          </TabsContent>
          <TabsContent value="menu" className="mt-6">
            <MenuTab />
          </TabsContent>
          <TabsContent value="transportation" className="mt-6">
            <TransportationTab />
          </TabsContent>
          <TabsContent value="transport-calendar" className="mt-6">
            <TransportationCalendar />
          </TabsContent>
          <TabsContent value="transport-resources" className="mt-6">
            <TransportResourcesTab />
          </TabsContent>
          <TabsContent value="departments" className="mt-6">
            <DepartmentsTab />
          </TabsContent>
          <TabsContent value="meds" className="mt-6">
            <MedicationsTab residents={residents} />
          </TabsContent>
          <TabsContent value="map" className="mt-6">
            <FloorPlanTab />
          </TabsContent>
          <TabsContent value="staff" className="mt-6">
            <StaffTab staff={staff} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="kiosks" className="mt-6">
            <KiosksTab kiosks={kiosks} zones={zones} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="zones" className="mt-6">
            <ZonesTab zones={zones} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="family" className="mt-6">
            <FamilyTab residents={residents} />
          </TabsContent>
          <TabsContent value="tokens" className="mt-6">
            <DeviceTokensTab />
          </TabsContent>
          <TabsContent value="insights" className="mt-6">
            <Insights />
          </TabsContent>
          <TabsContent value="audit" className="mt-6">
            <AuditTab />
          </TabsContent>
          <TabsContent value="hardware" className="mt-6">
            <HardwareReceiptsTab />
          </TabsContent>
          <TabsContent value="escalation" className="mt-6">
            <EscalationTab />
          </TabsContent>
          {user?.role === "owner" && (
            <TabsContent value="facilities" className="mt-6">
              <FacilitiesTab
                autoOpenAdd={autoOpenFacilityDialog}
                onAutoOpenHandled={() => setAutoOpenFacilityDialog(false)}
                onChange={refreshFacilities}
              />
            </TabsContent>
          )}
          <TabsContent value="roadmap" className="mt-6">
            <Roadmap />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

