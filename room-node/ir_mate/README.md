# IR Mate (infrared blaster) — room TV/AC control

The Seeed XIAO IR Mate (ESP32-C3) sends infrared to a room's TV (later AC). It is one room device
of the platform: CAOSCare reaches it through Home Assistant with the `ir_blaster` device adapter
(`backend/device_ir_adapter.py`) and a brand code table (`backend/ir_codesets.py`).

- `caoscare_ir_mate.yaml` — Seeed's firmware config plus HA actions `send_sony/nec/samsung/lg/rc5/pronto/raw`
  and decoded-code logging. Build/flash: `esphome compile caoscare_ir_mate.yaml`, then
  `esphome upload --device <ip> caoscare_ir_mate.yaml` (over Wi-Fi keeps its stored Wi-Fi; a USB flash can erase it).
  ESPHome 2025.7.5 (newest for Python 3.10).
- First-time Wi-Fi: hold its button > 5 s (factory reset), join its hotspot "XIAO IR Mate"/"Seeed_ir"
  (password 12345678, Seeed default), open 192.168.4.1, choose the 2.4 GHz home network.
- Add to HA: ESPHome integration by IP (HA runs in a VM without Bluetooth/mDNS reach).
- Register a room's TV: `smart_devices` record with `protocol: "ir_blaster"`, `endpoint: "esphome.<device>"`,
  `ir_codeset: "<table>"`, capabilities `power, volume, volume_step, mute`.
- Known: the top is a touch sensor (sends slot 0 and vibrates); learned recordings of long codes truncate —
  use code tables instead. Infrared is one-way: CAOSCare never claims a TV state it cannot see.
- Placement/power and the required TV audio/wake acceptance matrix are in
  `docs/TV_AUDIO_AND_WAKE_SETUP_MANUAL.md`. In particular, TV USB power is usable only when that port stays
  powered in standby; a state-reporting TV connection—not Bluetooth by name alone—is required for Aria to
  change volume during a conversation without guessing the level.

Proven 2026-10-12 on the Room 214 Sony Bravia: power on/off/on, volume 100 down + 50 up, volume steps via the room command path.
