# CAOS Care — Android RF Bridge App

**Purpose**: Run on a wall-mounted Android tablet with a USB RF receiver (or any USB-serial device that outputs JSON lines). Each pendant press is parsed and POSTed to the CAOS Care backend at `POST /api/pendants/event`, which looks up the pendant by frequency and pages staff.

---

## Hardware support (generic USB-serial)

This scaffold is intentionally receiver-agnostic. It works with **anything that speaks USB-serial / USB-CDC and emits JSON lines**, including:

- **Arduino Uno / Pro Micro / ESP32 + RFM69 or CC1101** (recommended open-source path for 900 MHz)
- **USB-UART bridges** (CP2102 / CH340 / FTDI)
- **RTL-SDR USB dongle** (paired with a small decoder program that outputs JSON)
- **Proprietary pager-system receivers** that expose a USB-serial port (tell us which; we'll add the protocol parser)

### Expected line protocol (one JSON object per line, newline-terminated)

```json
{"frequency_mhz": 916.1250, "signal_strength": 82, "battery_percent": 87, "event_type": "press"}
```

Valid `event_type`: `press` | `fall` | `periodic_ping`.

The app adds the tablet's configured `zone` before POSTing to the backend.

---

## Backend endpoint contract

```
POST {BACKEND_BASE}/api/pendants/event
Content-Type: application/json

{
  "frequency_mhz": 916.1250,
  "signal_strength": 82,
  "battery_percent": 87,
  "event_type": "press",         // or "fall" or "periodic_ping"
  "zone": "Hallway A",            // injected by the tablet
  "device_token": "..."           // reserved; HMAC guard coming in production
}
```

Response: the bridge does not care about the response; it logs success/failure.

---

## Project layout

```
android-bridge/
├── README.md                       (this file)
├── PROTOCOL.md                     (pendant RF pinout + framing notes)
├── build.gradle.kts                (Gradle Kotlin DSL - app module)
├── src/main/AndroidManifest.xml
├── src/main/java/com/caoscare/bridge/
│   ├── MainActivity.kt              (status screen + zone config)
│   ├── BridgeService.kt             (foreground service — reads serial, POSTs events)
│   ├── UsbSerialReader.kt           (USB-serial open / line reader)
│   ├── CaosApi.kt                   (Retrofit/OkHttp client)
│   └── Settings.kt                  (SharedPreferences: backend_url, zone, device_token)
├── src/main/res/xml/device_filter.xml (USB vendor/product whitelist)
└── src/main/res/layout/activity_main.xml
```

---

## Build

Requires Android Studio Hedgehog+ and targets Android 9+ (API 28). Uses [usb-serial-for-android](https://github.com/mik3y/usb-serial-for-android) 3.7.0.

```bash
./gradlew :app:installDebug
```

---

## First-run setup

1. Install APK on the tablet.
2. Plug in the USB receiver (USB-OTG adapter if needed). The tablet prompts to grant USB permission — accept.
3. Open CAOS Bridge. In Settings:
   - **Backend URL**: `https://your-caos-deployment.com`
   - **Zone**: the zone the tablet lives in (e.g. "Hallway A"). This is what gets attached to every pendant event.
   - **Device token** (optional): reserved for production HMAC auth.
4. Tap **Start bridge**. A persistent notification shows "CAOS Bridge — listening". Any JSON line received on the serial port is parsed and posted.

## Testing without hardware

Use `adb` to push sample JSON through a USB-TTY loopback, or use the **Simulate press** button in the Admin → Pendants tab of the CAOS Care web app.

---

## Python RF bridge (`caos_rf_bridge.py`)

The SDR bridge used on the EliteDesk: runs `rtl_433` on the configured bands
and posts decoded presses to the backend. Three files, deployed together:

| File | Role |
|---|---|
| `caos_rf_bridge.py` | Entry point: config, backend calls, capture polling, `on_record` |
| `sdr_control.py` | Spawns `rtl_433`, reads its JSON, stall watchdog, USB reset of the SDR |
| `rf_restart_policy.py` | When to respawn `rtl_433` and what to log |

**Restart backoff.** A run counts as healthy if `rtl_433` stayed up at least
30 s (`CAOS_HEALTHY_RUN_SECONDS`) or decoded a record. After a healthy run the
next spawn is immediate, so the 90 s stall watchdog (`CAOS_WATCHDOG_SECONDS`)
behaves as before. After a failed run (e.g. no SDR plugged in: `rtl_433`
exits within a second with "No supported devices found.") the bridge waits
1, 2, 5, 10, 30, then 60 s between spawns. SIGINT/SIGTERM end a wait at once.

**Logging while failing.** The first failure is logged in full (spawn line,
`rtl_433` output, reason). Repeats of the same failure print one status line
every 300 s (`CAOS_RESTART_STATUS_SECONDS`); a different failure is logged in
full again; recovery prints one line. Before this, a missing SDR respawned
`rtl_433` about 40 times a second and wrote about 4 GB of log a day.

**Tests:** `python -m pytest android-bridge/tests` (needs `pytest` and
`requests`; uses stand-in `rtl_433` scripts, no SDR or backend).

**Service template:** `caos-rf-bridge.service.example` is a systemd user unit
that logs to the journal. It is not installed anywhere.
