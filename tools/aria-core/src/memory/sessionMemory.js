const fs = require("fs");
const path = require("path");

const DEFAULT_RUNTIME_DIR = path.join(__dirname, "..", "..", "runtime");

function safeSessionId(sessionId) {
  return String(sessionId || "default").replace(/[^a-zA-Z0-9._-]/g, "_");
}

function createSessionMemory({ runtimeDir = process.env.ARIA_RUNTIME_DIR || DEFAULT_RUNTIME_DIR } = {}) {
  const sessionsDir = path.join(runtimeDir, "sessions");
  fs.mkdirSync(sessionsDir, { recursive: true });

  function sessionPath(sessionId) {
    return path.join(sessionsDir, `${safeSessionId(sessionId)}.jsonl`);
  }

  function append(sessionId, entry) {
    const record = { ts: new Date().toISOString(), ...entry };
    fs.appendFileSync(sessionPath(sessionId), JSON.stringify(record) + "\n", "utf8");
    return record;
  }

  function read(sessionId, { maxLines = 40 } = {}) {
    const file = sessionPath(sessionId);
    if (!fs.existsSync(file)) return [];
    const lines = fs.readFileSync(file, "utf8").trim().split("\n").filter(Boolean);
    return lines.slice(-maxLines).map((line) => {
      try { return JSON.parse(line); }
      catch { return { type: "corrupt", raw: line }; }
    });
  }

  return { append, read };
}

module.exports = { createSessionMemory };
