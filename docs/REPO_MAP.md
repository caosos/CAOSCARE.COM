# CAOS Care Repo Map

## Purpose

This map makes the CAOS Care repository inspectable by future AI agents and human builders.

It is the current source-orientation document for the repository. Future agents must update this file when major frontend, backend, Android, hardware, documentation, or memory architecture changes are added.

## Verified repository state

```text
Repository: caosos/CAOSCARE.COM
Default branch: main
Visibility: public
Primary role: CAOS Care product/build surface
Status: active multi-surface repository
```

## Correction notice

An earlier onboarding map treated this repository as mostly documentation-only and stated that actual frontend/backend code should be mapped later when code exists.

That is no longer accurate.

Current inspection confirms this repository already contains:

```text
frontend web application surfaces
backend FastAPI service surfaces
Android companion application surfaces
Android bridge / RF integration surfaces
Android vision application surfaces
memory / PRD documentation
agent onboarding documentation
```

Future agents must not treat this repository as blank or documentation-only.

## Mandatory first-read order

Before modifying this repository, read:

```text
README.md
AGENTS.md
docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md
docs/REPO_MAP.md
```

Then inspect the specific files relevant to the requested task.

## Top-level architecture map

```text
README.md                                      Public repo entrypoint
AGENTS.md                                      Mandatory AI/build-agent operating protocol
docs/                                          Governance, onboarding, repo map, future contracts
memory/                                        Product requirement / memory doctrine artifacts
frontend/                                      Web application frontend
backend/                                       FastAPI backend and domain routes
android-companion/                             Android companion / RF bridge companion surface
android-bridge/                                Android RF bridge / protocol support surface
android-vision/                                Android vision / voice assistance surface
.emergent/                                     Emergent-generated summary/metadata surface
```

## Frontend map

Verified frontend page surfaces include:

```text
frontend/src/pages/Landing.jsx                 Public landing / product entry page
frontend/src/pages/Login.jsx                   Staff/admin login surface
frontend/src/pages/Admin.jsx                   Admin surface
frontend/src/pages/AdminLogin.jsx              Admin login surface
frontend/src/pages/StaffDashboard.jsx          Staff dashboard surface
frontend/src/pages/FamilyPortal.jsx            Family portal surface
frontend/src/pages/FamilyTab.jsx               Family-facing tab/surface
frontend/src/pages/ClinicianTab.jsx            Clinician-facing tab/surface
frontend/src/pages/Kiosk.jsx                   Resident/kiosk interaction surface
frontend/src/pages/InstallKioskWizard.jsx      Kiosk installation workflow surface
frontend/src/pages/RealtimeChatScreen.jsx      Realtime chat/voice interaction surface
frontend/src/pages/Blueprint.jsx               Blueprint/architecture display surface
frontend/src/pages/HelpHub.jsx                 Help/onboarding support surface
frontend/src/index.css                         Global frontend styling
```

Observed frontend product claims and UX direction include:

```text
senior living / life-safety AI framing
one-press call / room-mounted tablet concept
voice companion concept
staff dashboard concept
building-wide location / mesh concept
low-vision / large touch target emphasis
900 MHz / existing pendant infrastructure direction
kiosk demo and staff sign-in paths
```

Important: public marketing copy and regulated/safety-sensitive claims must stay bounded by the CAOS Care safety doctrine. Do not add medical-device, clinical-authority, autonomous emergency-dispatch, or guaranteed-compliance claims unless Michael explicitly authorizes and the required legal/regulatory basis exists.

## Backend map

Verified backend service entrypoint:

```text
backend/server.py                               FastAPI app, /api router, health endpoint, route registration
backend/models.py                               Pydantic domain models and input schemas
```

Verified/observed backend route domains registered from `backend/server.py` include:

```text
auth
residents
staff
kiosks
alerts
location
ai
pendants
roadmap
insights
notifications
wearables
device_auth
family_portal
devices
vision
tasks
haiku
paging
medications
memory
audit
realtime
rf
facilities
hardware
escalation
research
weather
timers
```

The backend exposes at least:

```text
GET /api/           service/status root
GET /api/health     database health check
```

Backend implementation notes visible from inspected code:

```text
FastAPI application
APIRouter prefix /api
CORS middleware configured from CORS_ORIGINS or wildcard fallback
startup seed hook via lifespan
Mongo-style db ping through deps.db
```

## Domain model map

Verified model/domain concepts include:

```text
Facility
User / auth inputs
Resident / participation levels / preferences / resident memory
ClinicalThresholds
Kiosk
Zone
Alert / alert category / acknowledgement / resolution / escalation fields
LocationUpdate
ChatMessage / ChatInput / TTSInput
Pendant / PendantEventInput
RoadmapItem
Insight
Notification
FamilyContact
Wearable / WearableEventInput
DeviceToken
SmartDevice / DeviceCommandInput
VisionFrameInput / VisionSessionStart
StaffTask / StaffTaskTemplate
ResidentMemory
RF fingerprint / capture / pairing / event ingest
HardwareDevice / capability probe concepts
```

Safety note: model names and schemas may include medical-adjacent fields such as medications, clinical thresholds, alerts, vitals, and behavior-change signals. These must remain assistive/advisory unless explicit regulatory and clinical authority exists.

## Android / device map

Verified Android and bridge surfaces include:

```text
android-companion/                              Android companion app surface
android-companion/README.md                    Companion app documentation
android-companion/build.gradle.kts             Android build configuration
android-companion/app/src/main/kotlin/care/caos/companion/CompanionApp.kt
android-companion/app/src/main/kotlin/care/caos/companion/ui/AppRoot.kt
android-companion/app/src/main/kotlin/care/caos/companion/ui/DashboardScreen.kt
android-companion/app/src/main/kotlin/care/caos/companion/ui/ProvisionScreen.kt
android-companion/app/src/main/kotlin/care/caos/companion/service/RfBridgeService.kt
android-companion/app/src/main/kotlin/care/caos/companion/service/BridgeApi.kt
android-companion/app/src/main/kotlin/care/caos/companion/rtl433/Rtl433Bridge.kt
android-companion/app/src/main/cpp/rtl433_jni.cpp
android-companion/app/src/main/res/values/strings.xml

android-bridge/                                Android bridge / RF protocol surface
android-bridge/README.md                       Bridge documentation
android-bridge/PROTOCOL.md                     Bridge/RF protocol documentation
android-bridge/caos_rf_bridge.py               Python RF bridge helper
android-bridge/app/src/main/java/com/caoscare/bridge/BridgeService.kt
android-bridge/app/src/main/java/com/caoscare/bridge/CaosApi.kt
android-bridge/app/src/main/java/com/caoscare/bridge/Settings.kt
android-bridge/app/src/main/res/layout/activity_main.xml

android-vision/                                Android vision app surface
android-vision/README.md                       Vision app documentation
android-vision/app/src/main/java/care/caos/vision/MainActivity.kt
android-vision/app/src/main/java/care/caos/vision/VisionUploader.kt
android-vision/app/src/main/java/care/caos/vision/AudioPlayback.kt
```

Device direction currently spans:

```text
resident kiosk/tablet
staff dashboard/tablet workflow
pendant/RF bridge
wearable gateway concepts
vision/audio assistance
hardware capability probing
```

## Memory / product doctrine map

Verified memory/product docs include:

```text
memory/PRD.md
memory/PRD_HUB_v1.md
```

Use these as product-source artifacts, not as proof that every described feature is production-complete. Feature completion requires source inspection, visible behavior, backend route support, acceptance criteria, and preferably smoke/regression evidence.

## Documentation map

Verified governance/onboarding docs include:

```text
README.md
AGENTS.md
docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md
docs/REPO_MAP.md
```

Recommended companion contracts still worth adding or expanding when needed:

```text
docs/CAOS_CARE_PRODUCT_CONTRACT.md
docs/CAOS_CARE_HARDWARE_CONTRACT.md
docs/CAOS_CARE_PRIVACY_SAFETY_CONTRACT.md
docs/CAOS_CARE_UX_BEHAVIOR_CONTRACT.md
docs/BUILD_STATUS.md
docs/TROUBLESHOOTING_VAULT.md
docs/FEATURE_PARITY_MATRIX.md
docs/API_SURFACE_MAP.md
docs/ANDROID_DEVICE_MAP.md
docs/DEPLOYMENT_RUNBOOK.md
```

## Website status

The repository contains a frontend landing page and related web application pages.

However, a live public CAOSCARE.COM website crawl was previously not available from ChatGPT tooling. Future agents must distinguish:

```text
verified repo frontend content
verified deployed website content
Michael-provided product direction
inferred architecture
planned features
```

Do not invent live website state. If the live site is needed, inspect the deployed site directly and record the result here or in a dedicated website audit document.

## Feature/source verification standard

A feature may be described as implemented only when the agent verifies at least one of:

```text
source file/module exists and contains the relevant behavior
backend route/model/schema exists and supports the behavior
frontend route/component renders the behavior
Android/device code supports the behavior
manual smoke path or test evidence exists
```

Otherwise mark the capability as:

```text
planned
concept
partially implemented
repo-visible but unverified at runtime
pending live validation
```

## Product capability buckets

Current repo-visible capability buckets include:

```text
resident profiles and memory
staff dashboard / tasking
kiosk interaction
alerts and escalation
location / zone awareness
pendant / RF ingest
wearable event ingest
family portal
notifications
AI chat / TTS / vision assistance
hardware/device registry concepts
facility / multi-tenant root concepts
roadmap / blueprint / help surfaces
```

## Safety boundaries

CAOS Care is not a replacement for clinicians, caregivers, licensed medical professionals, emergency services, or regulated clinical judgment.

Allowed default posture:

```text
assistive
advisory
human-supervised
receipt-backed
privacy-aware
operationally useful
```

Disallowed unless explicitly authorized and legally/regulatorily supported:

```text
autonomous diagnosis
autonomous medication authority
autonomous clinical orders
autonomous emergency dispatch
medical-device claims
legal/compliance guarantees
selling or exposing private resident/staff/family data
```

## Current open work

```text
1. Inspect live deployed CAOSCARE.COM site when reachable.
2. Add or update BUILD_STATUS.md with actual runtime/build/deploy status.
3. Add API_SURFACE_MAP.md by inspecting backend/routes/*.py.
4. Add ANDROID_DEVICE_MAP.md by inspecting android-companion, android-bridge, and android-vision.
5. Add privacy/safety contract specific to resident/staff/family data flows.
6. Add hardware/device contract covering kiosk, RF bridge, wearables, and vision surfaces.
7. Add feature parity matrix separating repo-visible, runtime-verified, planned, and blocked capabilities.
8. Add smoke/regression checklist for frontend, backend, and Android surfaces.
```

## Search terms for future agents

```text
resident
care plan
staff
handoff
reminder
alert
fall
geofence
wearable
kiosk
dock
tablet
predictive
behavior change
receipt
privacy
consent
family
incident
pendant
rf
rtl433
vision
tts
memory
facility
hardware
escalation
notification
```

## Non-negotiable

Do not infer implemented runtime behavior from desired product direction.

Do not infer live deployment state from repository existence.

Do not treat this repo as blank.

This repository is an active CAOS Care multi-surface codebase. Keep the map current, inspect before writing, preserve human oversight, and maintain strict care-domain safety boundaries.
