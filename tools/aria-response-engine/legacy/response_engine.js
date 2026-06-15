const fs = require("fs");
const path = require("path");
const OpenAI = require("openai");

const fileEngine = require("../file-engine/file_engine");
const { readSession } = require("./memory/session_reader");
const { writeSession } = require("./memory/session_writer");
const { authorityDecision } = require("./authority/decision_layer");

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

const MODEL = process.env.OPENAI_MODEL || "gpt-4o-mini";

const IDENTITY_PATH = path.join(__dirname, "..", "..", "identity", "aria_identity.json");
const CAPABILITIES_PATH = path.join(__dirname, "..", "..", "state", "capabilities.json");

let ARIA_IDENTITY = null;
let CAPABILITY_TRUTH = null;

function fatal(msg, err) {
  console.error("FATAL:", msg);
  if (err) console.error(err.message || err);
  process.exit(1);
}

function safeJson(x) {
  try { return JSON.stringify(x, null, 2); }
  catch { return JSON.stringify({ ok: false, error: "json_stringify_failed" }); }
}

function formatTimestamp() {
  const now = new Date();
  const tz = "America/Chicago";
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
  const parts = Object.fromEntries(fmt.formatToParts(now).map(p => [p.type, p.value]));
  return `⏰ ${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} (${tz})`;
}

try {
  ARIA_IDENTITY = fs.readFileSync(IDENTITY_PATH, "utf8").trim();
} catch (err) {
  fatal("Unable to load ARIA identity", err);
}

try {
  CAPABILITY_TRUTH = fs.readFileSync(CAPABILITIES_PATH, "utf8").trim();
} catch (err) {
  fatal("Unable to load capability manifest", err);
}

const TOOLS = [
  {
    type: "function",
    function: {
      name: "file_read",
      parameters: {
        type: "object",
        properties: { path: { type: "string" } },
        required: ["path"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "file_write",
      parameters: {
        type: "object",
        properties: {
          path: { type: "string" },
          content: { type: "string" },
          overwrite: { type: "boolean" }
        },
        required: ["path", "content"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "file_list",
      parameters: {
        type: "object",
        properties: { path: { type: "string" } }
      }
    }
  }
];

async function executeTool(tc) {
  const name = tc.function.name;
  let args = {};
  try { args = JSON.parse(tc.function.arguments || "{}"); }
  catch { return { ok: false, error: "INVALID_TOOL_ARGS_JSON" }; }

  try {
    if (name === "file_read") {
      return { ok: true, ...(await fileEngine.readFile(args.path)) };
    }
    if (name === "file_write") {
      return {
        ok: true,
        ...(await fileEngine.writeFile(args.path, args.content, {
          overwrite: !!args.overwrite
        }))
      };
    }
    if (name === "file_list") {
      return { ok: true, ...(await fileEngine.listDirectory(args.path || ".")) };
    }
    return { ok: false, error: `UNKNOWN_TOOL:${name}` };
  } catch (err) {
    return { ok: false, error: err.message || String(err) };
  }
}

/**
 * Normalize CAOS session memory into OpenAI-compatible messages.
 * Truth-preserving. No invention.
 */
function normalizeSession(sessionEntries = []) {
  const out = [];
  for (const e of sessionEntries) {
    if (!e || !e.type) continue;
    if (e.type === "input") out.push({ role: "user", content: String(e.message ?? "") });
    if (e.type === "response") out.push({ role: "assistant", content: String(e.message ?? "") });
  }
  return out;
}

async function generateResponse(input, { sessionId = "default" } = {}) {
  let artifactResult = null;

  // 1) Truthful session write: user input
  try {
  // === AUTHORITY DECISION LAYER (ADL) ===
  try {
    const __adl = await authorityDecision({ sessionId, rawUserInput: input });
    if (__adl && __adl.handled) {
      writeSession(sessionId, { ts: new Date().toISOString(), type: "response", message: __adl.responseText });
      return __adl.responseText;
    }
  } catch {
    writeSession(sessionId, { ts: new Date().toISOString(), type: "response", message: "UNKNOWN" });
    return "UNKNOWN";
  }
  // === END ADL ===
    writeSession(sessionId, { ts: new Date().toISOString(), type: "input", message: String(input ?? "") });
  } catch {}

  // 2) Rolling working set: last 500KB / 200 lines
  const rawSession = readSession(sessionId, { maxBytes: 512 * 1024, maxLines: 200 });

  // Artifact detection (explicit user request only)

  const sessionMessages = normalizeSession(rawSession);

  const messages = [
    { role: "system", content: ARIA_IDENTITY },
    { role: "system", content: CAPABILITY_TRUTH },

    // Rule for graceful degradation under unknowns / batches
    {
      role: "system",
      content:
        "RULE: Maintain truthful continuity using provided session messages. " +
        "If a question is unknown/uncertain, say so and continue answering others. " +
        "Never stop the entire response due to a single unknown."
    },

    ...sessionMessages,
    { role: "user", content: String(input ?? "") }
  ];

  for (let i = 0; i < 3; i++) {
    const completion = await client.chat.completions.create({
      model: MODEL,
      tools: TOOLS,
      tool_choice: "auto",
      messages
    });

    const msg = completion.choices[0].message;

    if (!msg.tool_calls) {
      const ts = formatTimestamp();


      const body = (msg.content || "").trim();

      // 3) Truthful session write: assistant response
      try {
        writeSession(sessionId, { ts: new Date().toISOString(), type: "response", message: body });
      } catch {}

      return `${ts}\nAria:\n${body}`;
    }

    messages.push({ role: "assistant", tool_calls: msg.tool_calls });

    for (const tc of msg.tool_calls) {
      const result = await executeTool(tc);
      messages.push({
        role: "tool",
        tool_call_id: tc.id,
        content: safeJson(result)
      });
    }
  }

  const ts = formatTimestamp();

  return `${ts}\nAria:\n${body}`;
}

module.exports = { generateResponse };
