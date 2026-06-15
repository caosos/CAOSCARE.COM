function wantsClimateControl(input) {
  const text = String(input || "").toLowerCase();
  return (
    text.includes("cool") ||
    text.includes("air conditioner") ||
    text.includes("a/c") ||
    text.includes("ac") ||
    text.includes("heat") ||
    text.includes("temperature")
  );
}

function createMockProvider() {
  return {
    name: "mock",
    async generate({ input, capabilityRegistry }) {
      const ha = capabilityRegistry.homeAssistantStatus();

      if (wantsClimateControl(input)) {
        if (!ha.configured || !ha.adapterEnabled || ha.devices.length === 0) {
          return [
            "I know Home Assistant is the planned device-control layer, but it is not configured yet.",
            "I do not have a Home Assistant server, token, or registered A/C device, so I cannot cool the house right now.",
            "Give me the A/C brand/model or app name and I can add it to setup inventory before any control attempt."
          ].join(" ");
        }
      }

      return [
        "I am ARIA core running in capability-aware mock mode.",
        "I can chat and record receipts, but I will not claim device control unless a real configured adapter completes the action.",
        `Home Assistant status: ${ha.status}. Registered controllable devices: ${ha.devices.length}.`
      ].join(" ");
    }
  };
}

module.exports = { createMockProvider };
