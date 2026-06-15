async function authorityDecision({ input }) {
  const text = String(input || "").trim();

  if (!text) {
    return { handled: true, responseText: "I need a command or question before I can act." };
  }

  return { handled: false };
}

module.exports = { authorityDecision };
