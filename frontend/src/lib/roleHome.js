// Single source of truth for "where does this user land after sign-in" -
// was duplicated as an inline ternary across Landing/Login/AdminLogin/
// GoogleSignIn, which is exactly the kind of drift that caused the
// front_desk role to need adding in four places instead of one.
//
// Takes the whole user object (not just role) because a plain `staff` user
// now routes by their Department (User.department, a Department.slug):
// operational departments get their own workspace, care/nursing and
// unassigned staff get the resident-assistance board.

// Department slugs that route to the shared operational workspace
// (/workspace renders the department-appropriate view). These are the
// seeded Department slugs from routes/departments.py; "nursing" is
// deliberately absent - care staff land on the alert/assistance board.
const WORKSPACE_DEPARTMENTS = new Set([
  "maintenance",
  "housekeeping",
  "transportation",
  "kitchen",
]);

export function roleHomePath(user) {
  const role = user?.role;
  if (role === "front_desk") return "/front-desk";
  if (role === "owner" || role === "admin") return "/admin";
  // Plain staff: route by department.
  if (WORKSPACE_DEPARTMENTS.has(user?.department)) return "/workspace";
  // care/nursing, administration, or no department -> resident-assistance board
  return "/staff";
}

export function roleHomeLabel(user) {
  const role = user?.role;
  if (role === "front_desk") return "Continue to front desk";
  if (role === "owner" || role === "admin") return "Continue to admin";
  if (WORKSPACE_DEPARTMENTS.has(user?.department)) return "Continue to workspace";
  return "Continue to dashboard";
}
