import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import WorkAsIdentityNotice from "../WorkAsIdentityNotice";

test("keeps the real principal distinct from the temporary department authority", () => {
  const html = renderToStaticMarkup(
    <WorkAsIdentityNotice
      principal={{ user_id: "owner_1", name: "Michael", role: "owner" }}
      context={{
        work_context_id: "wctx_1", principal_role: "owner",
        acting_role: "staff", acting_department: "maintenance",
      }}
      departmentLabel="Maintenance"
    />
  );

  expect(html).toContain("Michael (owner)");
  expect(html).toContain("Working in Maintenance as Staff");
  expect(html).toContain("not as a simulated worker");
});

test("does not show outside an active Work-as context", () => {
  const html = renderToStaticMarkup(
    <WorkAsIdentityNotice principal={{ name: "Michael" }} context={null} />
  );
  expect(html).toBe("");
});
