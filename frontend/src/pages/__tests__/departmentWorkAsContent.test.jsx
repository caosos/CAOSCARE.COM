import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

let mockContext = null;

jest.mock("../../lib/auth", () => ({
  useAuth: () => ({ user: { user_id: "owner_1", name: "Michael", role: "owner" }, logout: jest.fn() }),
}));
jest.mock("../../lib/api", () => ({ api: { get: jest.fn(() => Promise.resolve({ data: [] })) } }));
jest.mock("../../lib/workContext", () => ({ useWorkContext: () => mockContext }));
jest.mock("react-router-dom", () => ({
  Link: ({ children }) => <span>{children}</span>,
  useNavigate: () => jest.fn(),
}), { virtual: true });
jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../TasksTab", () => ({ MyTasksCard: () => null }));
jest.mock("../MaintenanceWorkspace", () => () => null);
jest.mock("../TransportationCalendar", () => () => null);
jest.mock("../DepartmentQueue", () => () => null);
jest.mock("../../components/UpcomingSchedule", () => () => null);
jest.mock("../../components/WorkAsControl", () => () => null);
jest.mock("../../components/WorkAsIdentityNotice", () => () => null);
jest.mock("../CommunityServicesWorkspace", () => ({ department }) => (
  <div data-testid={`specialized-${department}`}>{department} specialized workspace</div>
));

import DepartmentWorkspace from "../DepartmentWorkspace";

test.each(["kitchen", "activities"])(
  "Work-as opens the specialized %s content workspace",
  (department) => {
    mockContext = {
      work_context_id: `wctx_${department}`,
      principal_role: "owner",
      acting_role: "staff",
      acting_department: department,
    };
    const html = renderToStaticMarkup(<DepartmentWorkspace />);
    expect(html).toContain(`data-testid="specialized-${department}"`);
    expect(html).not.toContain(`${department} requests`);
  },
);
