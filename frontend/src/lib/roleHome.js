// Single source of truth for "where does this role land after sign-in" -
// was duplicated as an inline ternary across Landing/Login/AdminLogin/
// GoogleSignIn, which is exactly the kind of drift that caused the
// front_desk role to need adding in four places instead of one.
export function roleHomePath(role) {
  if (role === "front_desk") return "/front-desk";
  if (role === "owner" || role === "admin") return "/admin";
  return "/staff";
}

export function roleHomeLabel(role) {
  if (role === "front_desk") return "Continue to front desk";
  if (role === "owner" || role === "admin") return "Continue to admin";
  return "Continue to dashboard";
}
