#!/usr/bin/env node
const { generateResponse } = require("../src/generateResponse");

async function main() {
  const input = process.argv.slice(2).join(" ").trim();

  if (!input) {
    console.error("Usage: node tools/aria-core/cli/aria.js \"Aria, cool the house down\"");
    process.exit(2);
  }

  const result = await generateResponse(input, {
    sessionId: process.env.ARIA_SESSION_ID || "cli"
  });

  console.log(`⏰ ${result.timestamp}`);
  console.log("Aria:");
  console.log(result.responseText);
}

main().catch((err) => {
  console.error("ARIA core failed:", err.message || err);
  process.exit(1);
});
