/**
 * Dev-server API proxy (Admin lane).
 *
 * Why this exists: the Admin/Operations backend runs as a separate local
 * process (default 127.0.0.1:8001) so it never touches the Level-1 backend
 * on :8000. The browser that loads this dev server can only reach a fixed
 * set of forwarded host ports (3000 / 8000 / mongo) - a freshly-bound
 * :8001 is NOT reachable from the browser, only from this host. So instead
 * of pointing the frontend straight at :8001 (which fails with
 * "TypeError: Failed to fetch" and bounces every request to /admin-login),
 * the frontend talks to its OWN origin and the dev server - which runs on
 * this host and CAN reach :8001 - forwards /api to the Admin backend.
 *
 * This keeps every browser call same-origin (no CORS, cookies flow
 * normally) and keeps the Admin backend origin out of application source:
 * the target is an env var, and the frontend's REACT_APP_BACKEND_URL is
 * just its own dev origin.
 *
 * Not used by `craco build` / production - CRA only auto-loads this file
 * for `craco start`.
 */
const { createProxyMiddleware } = require("http-proxy-middleware");

const ADMIN_BACKEND_ORIGIN =
  process.env.ADMIN_BACKEND_ORIGIN || "http://127.0.0.1:8001";

module.exports = function (app) {
  app.use(
    "/api",
    createProxyMiddleware({
      target: ADMIN_BACKEND_ORIGIN,
      changeOrigin: true,
      xfwd: true,
      logLevel: "warn",
    })
  );
};
