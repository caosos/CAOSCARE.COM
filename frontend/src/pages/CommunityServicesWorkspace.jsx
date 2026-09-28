import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import DepartmentQueue from "./DepartmentQueue";
import MenuTab from "./MenuTab";
import ScheduleTab from "./ScheduleTab";

// Housekeeping, Kitchen and Activities staff workspaces. Every department
// gets its request queue (the shared DepartmentQueue over StaffTask with
// visibility_role === department); Kitchen also runs the menu and
// Activities the schedule - the same screens admins use under /admin.
const CONTENT = {
  kitchen: { label: "Menu", Screen: MenuTab },
  activities: { label: "Schedule", Screen: ScheduleTab },
};
const QUEUE_TITLE = {
  housekeeping: "Housekeeping requests",
  kitchen: "Dining requests",
  activities: "Activities requests",
};

export default function CommunityServicesWorkspace({ department }) {
  const queue = <DepartmentQueue department={department} title={QUEUE_TITLE[department] || "Requests"} />;
  const content = CONTENT[department];
  if (!content) return queue;
  const { label, Screen } = content;
  return (
    <Tabs defaultValue="requests" data-testid={`${department}-workspace`}>
      <TabsList>
        <TabsTrigger value="requests" data-testid="services-tab-requests">Requests</TabsTrigger>
        <TabsTrigger value="content" data-testid="services-tab-content">{label}</TabsTrigger>
      </TabsList>
      <TabsContent value="requests" className="mt-6">{queue}</TabsContent>
      <TabsContent value="content" className="mt-6"><Screen /></TabsContent>
    </Tabs>
  );
}
