# CAOS Vision — Android Companion App for AI Vision Glasses

This is the companion Android app for Vuzix M400 / M4000 smart glasses (or any
Android phone running Android 8+ with a camera). It captures frames from the
camera, optionally pairs with a resident's earbuds for audio, and streams
scenes to the CAOS Care backend which runs Claude Sonnet 4.5 image understanding
and OpenAI TTS.

## What it does

1. Captures a camera frame every ~4 seconds (or on a spoken "look" wake word).
2. Optionally records a short audio clip for a question.
3. Base64-encodes the JPEG and POSTs to
   `POST {CAOS_BASE_URL}/api/vision/describe` (for a generic describe) or
   `POST {CAOS_BASE_URL}/api/vision/frame` (for a spoken question).
4. Plays the returned TTS audio through the paired earbuds / bone-conduction
   headset.

## Pairing

- App is provisioned with a **Device Token** created in CAOS Care →
  Admin → Device tokens (scopes: *optional* for vision endpoints today).
- Base URL and token are stored in Android's EncryptedSharedPreferences.

## Target hardware

- Vuzix M400 / M4000 (Android 11, HUD display)
- Generic Android phone clipped to a lanyard (fallback)
- BLE pairing to the per-room wall kiosk (for offline-style handoff)

## Project layout

```
android-vision/
├── README.md                 ← you are here
├── build.gradle.kts          ← placeholder (Android Studio will regenerate)
├── app/
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/care/caos/vision/
│       │   ├── MainActivity.kt          ← camera preview + shutter loop
│       │   ├── VisionUploader.kt        ← POSTs frames to /api/vision/describe
│       │   └── WakeWordListener.kt      ← "Hey CAOS, what is that?" stub
│       └── res/
│           └── layout/activity_main.xml
```

## Build

```
cd android-vision
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Backend endpoints used

- `POST /api/vision/describe` — pure scene describe
- `POST /api/vision/frame`    — scene + spoken question

Both accept a JSON body `{ image_base64, question?, speak: true }` and return
`{ reply, audio_base64 }`.

## Roadmap (next iterations)

- [ ] On-device face detection so we only upload when a human is in frame
- [ ] Resident pairing — if Margaret is wearing these glasses, send her
      `resident_id` so Claude personalizes the voice and warnings
- [ ] Offline fallback using TFLite image captioning when network is down
- [ ] BLE handshake with the per-room kiosk for silent pass-through when
      the resident is standing in front of their own kiosk
