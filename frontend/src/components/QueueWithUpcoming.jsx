import React, { useCallback, useState } from "react";
import DepartmentQueue from "../pages/DepartmentQueue";
import UpcomingSchedule from "./UpcomingSchedule";
import { UPCOMING_DEPARTMENTS } from "../lib/upcomingSchedule";

// A department's request queue with its date-ordered "Upcoming" read beside it
// (GET /tasks/upcoming) for departments that plan work ahead. Same records;
// the queue is where work changes.
export default function QueueWithUpcoming({ department, title, adminMode = false }) {
  const [reloadKey, setReloadKey] = useState(0);
  const bump = useCallback(() => setReloadKey((k) => k + 1), []);   // a queue change refreshes Upcoming at once
  const queue = <DepartmentQueue department={department} title={title} adminMode={adminMode} onLoaded={bump} />;
  if (!UPCOMING_DEPARTMENTS.includes(department)) return queue;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" data-testid={`${department}-queue-with-upcoming`}>
      <section className="lg:col-span-2 min-w-0">{queue}</section>
      <section className="min-w-0"><UpcomingSchedule department={department} reloadKey={reloadKey} /></section>
    </div>
  );
}
