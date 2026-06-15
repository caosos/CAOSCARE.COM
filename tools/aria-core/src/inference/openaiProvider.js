function createOpenAIProvider({ apiKey = process.env.OPENAI_API_KEY, model = process.env.OPENAI_MODEL || "gpt-4o-mini" } = {}) {
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is required for the openai provider");
  }

  let OpenAI;
  try {
    OpenAI = require("openai");
  } catch (err) {
    throw new Error("The openai package is not installed. Run npm install in tools/aria-core before using the openai provider.");
  }

  const client = new OpenAI({ apiKey });

  return {
    name: "openai",
    async generate({ input, identity, capabilityRegistry, sessionEntries = [] }) {
      const messages = [
        { role: "system", content: identity },
        {
          role: "system",
          content:
            "Capability truth follows. You must obey it and never claim unavailable control succeeded.\n" +
            capabilityRegistry.summarizeForPrompt()
        },
        ...sessionEntries
          .filter((entry) => entry.type === "input" || entry.type === "response")
          .map((entry) => ({
            role: entry.type === "input" ? "user" : "assistant",
            content: String(entry.message || "")
          })),
        { role: "user", content: String(input || "") }
      ];

      const completion = await client.chat.completions.create({ model, messages });
      return (completion.choices?.[0]?.message?.content || "").trim();
    }
  };
}

module.exports = { createOpenAIProvider };
