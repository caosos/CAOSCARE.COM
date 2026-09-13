import { roleHomePath, roleHomeLabel, workspaceLabel, departmentWorkspaceLabel } from "../roleHome";

describe("roleHomePath", () => {
  test("owner and admin go to /admin regardless of department", () => {
    expect(roleHomePath({ role: "owner" })).toBe("/admin");
    expect(roleHomePath({ role: "admin", department: "maintenance" })).toBe("/admin");
  });

  test("front_desk goes to /front-desk", () => {
    expect(roleHomePath({ role: "front_desk" })).toBe("/front-desk");
    expect(roleHomePath({ role: "front_desk", department: "housekeeping" })).toBe("/front-desk");
  });

  test("operational departments route a plain staff user to /workspace", () => {
    for (const dept of ["maintenance", "housekeeping", "transportation", "kitchen"]) {
      expect(roleHomePath({ role: "staff", department: dept })).toBe("/workspace");
    }
  });

  test("care/nursing, administration, custom, or no department -> /staff", () => {
    expect(roleHomePath({ role: "staff", department: "nursing" })).toBe("/staff");
    expect(roleHomePath({ role: "staff", department: "administration" })).toBe("/staff");
    expect(roleHomePath({ role: "staff", department: "therapy" })).toBe("/staff");
    expect(roleHomePath({ role: "staff", department: null })).toBe("/staff");
    expect(roleHomePath({ role: "staff" })).toBe("/staff");
  });

  test("handles a null/undefined user without throwing", () => {
    expect(roleHomePath(null)).toBe("/staff");
    expect(roleHomePath(undefined)).toBe("/staff");
  });
});

describe("workspaceLabel / departmentWorkspaceLabel", () => {
  test("per-user: where sign-in lands them", () => {
    expect(workspaceLabel({ role: "owner" })).toBe("Admin command centre");
    expect(workspaceLabel({ role: "front_desk" })).toBe("Front desk");
    expect(workspaceLabel({ role: "staff", department: "maintenance" })).toBe("Maintenance workspace");
    expect(workspaceLabel({ role: "staff", department: "kitchen" })).toBe("Kitchen workspace");
    expect(workspaceLabel({ role: "staff", department: "nursing" })).toBe("Care / assistance board");
    expect(workspaceLabel({ role: "staff" })).toBe("Care / assistance board");
  });
  test("per-slug: for the Departments table", () => {
    expect(departmentWorkspaceLabel("housekeeping")).toBe("Housekeeping workspace");
    expect(departmentWorkspaceLabel("nursing")).toBe("Care / assistance board");
    expect(departmentWorkspaceLabel("administration")).toBe("Admin command centre");
    expect(departmentWorkspaceLabel("therapy")).toBe("General staff board");
  });
});

describe("roleHomeLabel", () => {
  test("labels match the destination", () => {
    expect(roleHomeLabel({ role: "owner" })).toBe("Continue to admin");
    expect(roleHomeLabel({ role: "front_desk" })).toBe("Continue to front desk");
    expect(roleHomeLabel({ role: "staff", department: "maintenance" })).toBe("Continue to workspace");
    expect(roleHomeLabel({ role: "staff", department: "nursing" })).toBe("Continue to dashboard");
    expect(roleHomeLabel({ role: "staff" })).toBe("Continue to dashboard");
  });
});
