const fs = require("fs");
const path = require("path");

const DEFAULT_RUNTIME_DIR = path.join(__dirname, "..", "..", "runtime");

function createReceiptWriter({ runtimeDir = process.env.ARIA_RUNTIME_DIR || DEFAULT_RUNTIME_DIR } = {}) {
  const receiptsDir = path.join(runtimeDir, "receipts");
  fs.mkdirSync(receiptsDir, { recursive: true });

  function writeReceipt(receipt) {
    const date = new Date().toISOString().slice(0, 10);
    const file = path.join(receiptsDir, `${date}.jsonl`);
    const record = {
      ts: new Date().toISOString(),
      ...receipt
    };
    fs.appendFileSync(file, JSON.stringify(record) + "\n", "utf8");
    return record;
  }

  return { writeReceipt };
}

module.exports = { createReceiptWriter };
