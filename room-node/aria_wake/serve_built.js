#!/usr/bin/env node
// Serves a PRODUCTION BUILD of the CAOSCare frontend for the wake endpoint's
// Room page, and proxies /api/* to the backend (same origin, websocket upgrade
// included). No npm dependencies. A git merge that changes frontend/src does
// not affect this page until `ctl.sh rebuild` swaps in a new build.
//   ARIA_WAKE_BUILD_DIR   build directory   (default ~/.cache/aria-wake/build)
//   ARIA_WAKE_PAGE_PORT   listen port       (default 3002)
//   ARIA_WAKE_BACKEND     backend origin    (default http://127.0.0.1:8092)
const http = require("http");
const net = require("net");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
  ".ico": "image/x-icon", ".map": "application/json", ".txt": "text/plain", ".woff2": "font/woff2",
  ".mp4": "video/mp4", ".webmanifest": "application/manifest+json",
};

function createServer({ buildDir, backend }) {
  const target = new URL(backend);
  const root = path.resolve(buildDir);

  function proxy(req, res) {
    const up = http.request({
      host: target.hostname, port: target.port || 80, method: req.method, path: req.url,
      headers: { ...req.headers, host: target.host },
    }, (r) => { res.writeHead(r.statusCode, r.headers); r.pipe(res); });
    up.on("error", (e) => { if (!res.headersSent) res.writeHead(502); res.end("backend unreachable: " + e.message); });
    req.pipe(up);
  }

  function resolveFile(urlPath) {
    let p = path.normalize(path.join(root, decodeURIComponent(urlPath.split("?")[0])));
    if (p !== root && !p.startsWith(root + path.sep)) return null;
    try { if (fs.statSync(p).isFile()) return p; } catch (e) { /* fall through */ }
    return null;
  }

  const server = http.createServer((req, res) => {
    if (req.url.startsWith("/api/") || req.url === "/api") return proxy(req, res);
    const file = resolveFile(req.url) || path.join(root, "index.html");
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(503); return res.end("build missing: " + root); }
      const ext = path.extname(file);
      const cache = file.includes(path.sep + "static" + path.sep) ? "public, max-age=31536000, immutable" : "no-cache";
      res.writeHead(200, { "Content-Type": TYPES[ext] || "application/octet-stream", "Cache-Control": cache });
      res.end(data);
    });
  });

  server.on("upgrade", (req, socket, head) => {
    if (!req.url.startsWith("/api/")) return socket.destroy();
    const up = net.connect(target.port || 80, target.hostname, () => {
      let raw = `${req.method} ${req.url} HTTP/1.1\r\n`;
      for (const [k, v] of Object.entries({ ...req.headers, host: target.host })) raw += `${k}: ${v}\r\n`;
      up.write(raw + "\r\n"); if (head && head.length) up.write(head);
      socket.pipe(up); up.pipe(socket);
    });
    up.on("error", () => socket.destroy());
    socket.on("error", () => up.destroy());
  });
  return server;
}

module.exports = { createServer };

if (require.main === module) {
  const buildDir = process.env.ARIA_WAKE_BUILD_DIR || path.join(process.env.HOME, ".cache/aria-wake/build");
  const port = Number(process.env.ARIA_WAKE_PAGE_PORT || 3002);
  const backend = process.env.ARIA_WAKE_BACKEND || "http://127.0.0.1:8092";
  createServer({ buildDir, backend }).listen(port, "127.0.0.1", () =>
    console.log(JSON.stringify({ serving: buildDir, port, backend })));
}
