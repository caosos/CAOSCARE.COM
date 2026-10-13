import fs from "fs";
import path from "path";

const kioskSource = fs.readFileSync(path.join(__dirname, "../../pages/Kiosk.jsx"), "utf8");

test("conversation start and end contain no automatic TV or speaker control", () => {
  expect(kioskSource).not.toMatch(/duckRoomAudio|restoreRoomAudio|mutedDevicesRef|callAudioDuck/);
  expect(kioskSource).not.toContain("TV auto-mute");
});

test("explicit resident-requested device commands remain wired", () => {
  expect(kioskSource).toContain("await sendRoomDeviceCommand(kiosk.room, action, value, kind, deviceId)");
  expect(kioskSource).toContain("<RoomDevicePanel devices={devices}");
});
