const { createMockProvider } = require("./mockProvider");
const { createOpenAIProvider } = require("./openaiProvider");

function createInferenceProvider({ provider = process.env.ARIA_PROVIDER || "mock", options = {} } = {}) {
  const normalized = String(provider || "mock").toLowerCase();

  if (normalized === "mock") return createMockProvider(options);
  if (normalized === "openai") return createOpenAIProvider(options);

  throw new Error(`Unknown ARIA inference provider: ${provider}`);
}

module.exports = { createInferenceProvider };
