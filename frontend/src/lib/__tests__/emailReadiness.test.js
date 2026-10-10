// The panel text must never equate "configured" with working/verified.
import fs from "fs";
import path from "path";
const src = fs.readFileSync(path.join(__dirname, "../../components/EmailReadiness.jsx"), "utf8");
test("panel does not claim email works from configuration alone", () => {
  expect(src).toMatch(/does not mean email works/);
  expect(src).not.toMatch(/Everything needed is set/);
  expect(src).toMatch(/Sending domain verified at the provider/);
  expect(src).toMatch(/c\.state === "unknown"/);
});
test("sender states are told apart in the panel", () => {
  expect(src).toMatch(/default: "Resend default address"/);
  expect(src).toMatch(/invalid: "Invalid address"/);
});
