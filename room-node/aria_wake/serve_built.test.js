// Run: node --test room-node/aria_wake/serve_built.test.js
const test = require("node:test");
const assert = require("node:assert");
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { createServer } = require("./serve_built");

const get = (port, p, opts = {}) => new Promise((resolve, reject) => {
  const r = http.request({ port, path: p, host: "127.0.0.1", ...opts }, (res) => {
    let b = ""; res.on("data", (d) => (b += d)); res.on("end", () => resolve({ status: res.statusCode, body: b, headers: res.headers }));
  }); r.on("error", reject); r.end(opts.body);
});
const listen = (s) => new Promise((r) => s.listen(0, "127.0.0.1", () => r(s.address().port)));

test("static, SPA fallback, traversal, /api proxy", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wakebuild-"));
  fs.mkdirSync(path.join(dir, "static"));
  fs.writeFileSync(path.join(dir, "index.html"), "<html>INDEX</html>");
  fs.writeFileSync(path.join(dir, "static", "a.js"), "console.log(1)");
  fs.writeFileSync(path.join(path.dirname(dir), "secret.txt"), "nope");
  const stub = http.createServer((req, res) => { res.writeHead(200, { "x-seen": req.url }); res.end("stub:" + req.method); });
  const stubPort = await listen(stub);
  const srv = createServer({ buildDir: dir, backend: `http://127.0.0.1:${stubPort}` });
  const port = await listen(srv);
  try {
    let r = await get(port, "/static/a.js");
    assert.equal(r.status, 200); assert.match(r.headers["content-type"], /javascript/); assert.equal(r.body, "console.log(1)");
    r = await get(port, "/kiosk/kio_x?wake=1");
    assert.equal(r.status, 200); assert.equal(r.body, "<html>INDEX</html>");
    r = await get(port, "/../secret.txt");
    assert.equal(r.body, "<html>INDEX</html>");
    r = await get(port, "/api/health?x=1", { method: "POST", body: "{}" });
    assert.equal(r.body, "stub:POST"); assert.equal(r.headers["x-seen"], "/api/health?x=1");
    fs.writeFileSync(path.join(dir, "index.html"), "<html>NEW</html>");
    r = await get(port, "/");
    assert.equal(r.body, "<html>NEW</html>"); // swap is picked up without restart
    stub.close(); await new Promise((x) => setTimeout(x, 50));
    r = await get(port, "/api/x");
    assert.equal(r.status, 502);
  } finally { srv.close(); stub.close(); }
});
