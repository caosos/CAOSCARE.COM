const fs = require("fs");
const path = require("path");

const DEFAULT_CAPABILITIES_PATH = path.join(__dirname, "..", "..", "state", "capabilities.example.json");

function loadJson(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw);
}

function createCapabilityRegistry({ capabilitiesPath = process.env.ARIA_CAPABILITIES_PATH || DEFAULT_CAPABILITIES_PATH } = {}) {
  const capabilities = loadJson(capabilitiesPath);

  function homeAssistantStatus() {
    const ha = capabilities.home_assistant || {};
    return {
      configured: !!ha.configured,
      status: ha.status || "unknown",
      devices: Array.isArray(ha.devices) ? ha.devices : [],
      serverUrlConfigured: !!ha.server_url_configured,
      tokenConfigured: !!ha.token_configured,
      adapterEnabled: !!ha.adapter_enabled
    };
  }

  function hasControllableDevices() {
    const ha = homeAssistantStatus();
    return ha.configured && ha.adapterEnabled && ha.devices.length > 0;
  }

  function summarizeForPrompt() {
    return JSON.stringify(capabilities, null, 2);
  }

  return {
    capabilities,
    homeAssistantStatus,
    hasControllableDevices,
    summarizeForPrompt
  };
}

module.exports = { createCapabilityRegistry };
