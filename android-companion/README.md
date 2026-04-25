# CAOS Care Companion — Android Bridge App

A native Android application that turns any Android tablet into a CAOS Care kiosk hub:
listens to a USB-attached RTL-SDR (Nooelec NESDR SMArt v5), decodes sub-GHz button
presses (315 / 319 / 433 / 868 / 915 MHz), and forwards every press to the CAOS Care
backend so paired pendants auto-fire alerts.

Designed to replace the Termux + `caos_rf_bridge.py` workaround. Goals:

- **One-tap install** — sideload the APK, scan a QR code from `/admin/install`, done.
- **Zero baby-sitting** — runs as a foreground service, survives reboots, auto-reconnects.
- **Tamper-resistant** — kiosk-mode optional, signed builds only.
- **Plays well with the existing kiosk web UI** — both can run on the same tablet.

---

## Status

| Component | State |
|---|---|
| Gradle / Kotlin / Compose project shell | ✅ scaffolded |
| QR provisioning UI (parses payload from `/api/rf/kiosk/.../install-info`) | ✅ scaffolded |
| Foreground service (`RfBridgeService`) | ✅ scaffolded |
| HTTP client to backend (HMAC-signed `/api/rf/event`) | ✅ scaffolded |
| USB host claim of Nooelec | ✅ scaffolded (uses `UsbManager` + intent filter on VID 0x0bda PID 0x2832) |
| **Native rtl_433 decode (NDK / JNI)** | ⚠ **stub** — needs `rtl_433` source vendored under `app/src/main/cpp/rtl_433/` and a CMake build |
| Auto-update / Play Store | ⏭ next phase |
| MDM provisioning | ⏭ next phase |

The scaffolded code compiles and installs as a real APK *today*. The only piece that
isn't end-to-end yet is the native rtl_433 build — until that's vendored, the service
runs in "demo mode" emitting test events at 1 Hz so the rest of the pipeline can be
verified.

---

## Why a custom APK and not just Termux?

Termux gets you to "works on a developer's bench in 20 minutes" but breaks on:

- **Reboot** — Termux doesn't auto-restart unless `Termux:Boot` is sideloaded too.
- **Battery optimization** — Android kills it when backgrounded.
- **USB perms** — need to re-grant after every plug.
- **Updates** — no clean update channel; you `pip install -U` per device.
- **Fleet provisioning** — every device is hand-typed.

This APK fixes all of that.

---

## Build & install (manual)

```bash
cd /app/android-companion
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Or open in Android Studio (Hedgehog or later), let it sync, hit Run.

### Adding the native rtl_433 build

```bash
cd app/src/main/cpp
git clone --depth 1 https://github.com/merbanan/rtl_433.git
# edit CMakeLists.txt to include rtl_433 sources (template provided)
```

Then `./gradlew :app:assembleDebug` will pick up the NDK build automatically.

---

## Provisioning a kiosk

1. Sign in to the CAOS Care admin web UI as **owner** or **admin**.
2. Open **RF Pendants → Install bridge** (or visit `/admin/install/{kiosk_id}`).
3. Tap **Show QR** in the wizard (TODO — currently you copy the JSON manually).
4. Open the Companion APK on the tablet, tap **Scan provisioning code**.
5. The app stores `api_url`, `kiosk_id`, `rf_secret` and starts the service.
6. Plug in the Nooelec → green status dot in the app.
7. Press any pendant → event lands in the admin RF tab.

---

## Project layout

```
android-companion/
├── README.md                              ← you are here
├── settings.gradle.kts
├── build.gradle.kts                       ← root
├── gradle.properties
├── app/
│   ├── build.gradle.kts                   ← module
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── kotlin/care/caos/companion/
│       │   ├── CompanionApp.kt
│       │   ├── MainActivity.kt
│       │   ├── ui/
│       │   │   ├── ProvisionScreen.kt
│       │   │   └── DashboardScreen.kt
│       │   ├── data/
│       │   │   └── Settings.kt
│       │   ├── service/
│       │   │   ├── RfBridgeService.kt
│       │   │   └── BridgeApi.kt
│       │   ├── usb/
│       │   │   └── RtlSdrUsb.kt
│       │   └── rtl433/
│       │       └── Rtl433Bridge.kt        ← JNI loader (stub today)
│       ├── res/
│       │   ├── xml/usb_device_filter.xml  ← claim Nooelec VID/PID
│       │   └── values/strings.xml
│       └── cpp/
│           ├── CMakeLists.txt             ← vendor rtl_433 here
│           └── rtl433_jni.cpp             ← JNI shim
```

---

## License & signing

- App ID: `care.caos.companion`
- Sign with your release keystore before distributing. Don't check the keystore into git.
- Suggest GitHub Releases as the v1 sideload distribution channel; promote to Play
  Console once the native build is stable.
