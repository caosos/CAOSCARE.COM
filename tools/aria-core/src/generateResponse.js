const fs = require("fs");
const path = require("path");
const { createInferenceProvider } = require("./inference");
const { createCapabilityRegistry } = require("./capabilities/capabilityRegistry");
const { createSessionMemory } = require("./memory/sessionMemory");
const { authorityDecision } = require("./authority/decisionLayer");
const { createReceiptWriter } = require("./receipts/receiptWriter");

const DEFAULT_IDENTITY_PATH = path.join(__dirname, "..", "identity", "aria_identity.example.md");

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8").trim();
}

function formatTimestamp() {
  const now = new Date();
  const tz = process.env.ARIA_TIMEZONE || "America/Chicago";
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
  const parts = Object.fromEntries(fmt.formatToParts(now).map((p) => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} (${tz})`;
}

async function generateResponse(input, options = {}) {
  const sessionId = options.sessionId || "default";
  const identityPath = options.identityPath || process.env.ARIA_IDENTITY_PATH || DEFAULT_IDENTITY_PATH;
  const identity = readText(identityPath);
  const capabilityRegistry = createCapabilityRegistry(options);
  const memory = createSessionMemory(options);
  const receipts = createReceiptWriter(options);
  const provider = options.providerInstance || createInferenceProvider({
    provider: options.provider || process.env.ARIA_PROVIDER || "mock",
    options: options.providerOptions || {}
  });

  memory.append(sessionId, { type: "input", message: String(input || "") });

  const decision = await authorityDecision({ input, sessionId, capabilityRegistry });
  let body;
  let handledBy = provider.name;

  if (decision && decision.handled) {
    body = decision.responseText;
    handledBy = "authority";
  } else {
    const sessionEntries = memory.read(sessionId);
    body = await provider.generate({ input, identity, capabilityRegistry, sessionEntries });
  }

  const responseText = String(body || "").trim() || "I do not have enough information to answer truthfully yet.";
  memory.append(sessionId, { type: "response", message: responseText, provider: handledBy });

  const receipt = receipts.writeReceipt({
    sessionId,
    provider: handledBy,
    input: String(input || ""),
    response: responseText,
    capabilitySnapshot: capabilityRegistry.homeAssistantStatus()
  });

  return {
    ok: true,
    timestamp: formatTimestamp(),
    provider: handledBy,
    responseText,
    receipt
  };
}

module.exports = { generateResponse };
