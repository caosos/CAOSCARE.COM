import React from "react";
import DepartmentQueue from "./DepartmentQueue";

// Maintenance work orders: the shared department queue, plus the
// "New work order" form maintenance staff and admins use.
export default function MaintenanceWorkspace({ adminMode = false }) {
  return (
    <DepartmentQueue department="maintenance" title="Maintenance work orders" itemName="work order"
                     allowCreate adminMode={adminMode} />
  );
}
