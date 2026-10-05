# Pilot Hearing & Handset Requirements

**Status:** PROPOSED requirements for procurement and acceptance. Nothing in this document has been bought, installed or tested.
**Companion to:** `docs/HEARING_ASSISTANCE_PERSONAL_AUDIO_ARCHITECTURE.md`. That document holds the research. Its source labels (A1–A6, G1–G5, B1–B3, M1–M6, L1–L2) are reused here unchanged.
**Lane:** Round 5 Agent Six, RQ-009 phase 2. Branch `research/hearing-assistance-audio`, PR #53.
**Room baseline it fits:**
- central EliteDesk;
- Voice PE as the room voice endpoint;
- separate handset telephony: corded analog handset → ATA → Asterisk.

The handset path is the D2 decision (Michael, 2026-09-27) recorded in `docs/PILOT1_ROOM1_HARDWARE_INVENTORY.md` rows D5–D8.
**Research date:** 2026-10-04. New primary sources are listed in §6 (F1–F6).

Keywords: **MUST** = a fail blocks purchase or acceptance. **SHOULD** = expected; a deviation needs a written reason. **OPTIONAL** = nice to have.

---

## 1. Room handset

### 1.1 What the FCC actually requires (wireline telephones)

**Coverage**
- Every telephone made in or imported into the US after 1989-08-16 must be hearing aid compatible, as defined in 47 CFR §68.316. Cordless telephones are covered from 1991-08-16. Telephones used with public mobile services or private radio, and secure telephones, are exempt [F1].
- All telephones, including cordless, must have volume control per §68.317 [F2].

**Magnetic (telecoil) coupling** is the meaning of "HAC" for a wireline phone. §68.316 incorporates EIA RS-504 [F3]:
- Axial magnetic field at the measurement plane: greater than **−22 dB relative to 1 A/m**, for −10 dBV input at 1 kHz.
- Radial components at four points ≥16 mm off-axis: greater than **−27 dB re 1 A/m**.
- Induced-voltage frequency response must fall in the permitted region over **300–3300 Hz**.
- There is no M/T rating for wireline phones. M- and T-ratings are a wireless-handset scheme (§1.4).

**Volume control** for telephones made or imported on or after 2020-02-28, per §68.317(h) [F4]:
- At the loudest setting, the handset receiver must give **≥18 dB and ≤24 dB conversational gain**, measured per ANSI/TIA-4965-2012.
- The 18 dB minimum must be reached without significant clipping.
- **More than 24 dB is permitted only if the gain automatically resets to ≤24 dB on a proper on-hook transition.**

**Labeling:** registered telephones that are HAC per §68.316 must carry the letters **"HAC" permanently affixed** to the equipment [F5].

**Acoustic coupling:** wireline rules set no acoustic-coupling rating. For wireless handsets, acoustic coupling means the hearing aid's own microphone picks up the sound while RF interference is controlled [F6]. A corded analog handset has no cellular radio, so the RF-interference concern behind acoustic ratings does not arise in the same way. Acoustic use is covered by the volume and audio-quality requirements below.

What this means for procurement:
- "Hearing aid compatible" on a box is a regulatory minimum.
- It is **not** proof of a strong telecoil field or of enough loudness for profound loss.
- Verify the facts in §1.2 from the label and the manufacturer's documentation, then from the physical test (§4, HT-*).

### 1.2 Handset requirements

| ID | Requirement | Level | Basis / how verified |
|---|---|---|---|
| H-1 | Corded handset carries a permanent **"HAC"** mark (§68.300(b)) and the manufacturer declares compliance with 47 CFR §68.316 | MUST | [F1][F3][F5]. Inspect the label on the unit, not only the box. |
| H-2 | Manufacturer declares volume-control compliance with §68.317(h) / ANSI/TIA-4965 (18–24 dB, or more with auto-reset) | MUST | [F4]. Written spec sheet or declaration. |
| H-3 | If the handset gives **>24 dB** amplification, the gain resets to ≤24 dB on hang-up | MUST | [F4]. Safety for staff/visitors with normal hearing. Verified in HT-04. |
| H-4 | Amplification of **≥30 dB** available (amplified "senior" phone class) | SHOULD | Product judgment for a hearing-impaired population: 18 dB is only the legal floor. Pass only on a written spec value. |
| H-5 | Telecoil coupling confirmed by test: a resident's or a reference T-coil aid in T/MT mode hears call audio clearly with no buzz (HT-03) | MUST at acceptance | A label claim is not enough (directive). |
| H-6 | Tone/frequency adjustment (boost highs) on the receive path | SHOULD | Speech intelligibility for high-frequency loss. Verify on the spec sheet. |
| H-7 | **Visual ring indicator** (bright flashing light) | SHOULD | The resident may not hear the ringer. Verify that it works on **the ATA's ring signal** (HT-06): some indicators expect specific ring voltage or cadence. |
| H-8 | Loud ringer, adjustable to a high level | SHOULD | Same reason. |
| H-9 | **Speakerphone** | SHOULD | Allows a call when the handset is out of reach. **Caveat:** speakerphone audio plays into the room the Voice PE listens to (§2.3, rule R-5). |
| H-10 | Large buttons, high-contrast keys; one-touch memory keys for front desk / family | SHOULD | Matches the existing D5 requirement "corded, large-button". |
| H-11 | Behaviour on power loss is documented: does it still give dial tone and basic (unamplified) audio without its AC adapter? | MUST be **known** (not necessarily good) | Many amplified phones need AC power for amplification. The answer feeds the outage plan. Record UNKNOWN until verified (HT-07). |
| H-12 | Works with **warm-line** (off-hook auto-dial to Aria after a delay) and immediate-dial 0 / 911 through the selected ATA | MUST | D6 requirement. Verified in HT-08. |
| H-13 | Total **REN** of the phone and its indicator is within the ATA FXS port's supported ringer load | MUST | Values come from the two spec sheets. UNKNOWN until both models are chosen. |
| H-14 | Neckloop / 3.5 mm audio out jack | OPTIONAL | Lets a resident without a usable T-coil use their own neckloop. |
| H-15 | Caption-phone capability (IP CTS) | OPTIONAL / out of pilot scope | Separate FCC-regulated service. Not evaluated here. |

### 1.3 ATA + analog HAC handset vs native SIP HAC phone

**Recommendation for the pilot: ATA + corded analog HAC handset (keep D2).**

The reasons:
1. **Verifiability.** A registered analog telephone must carry a permanent "HAC" mark [F5], and its volume control falls under §68.317 [F2][F4].
   - That label rule applies to *registered* telephones. A SIP desk phone connects to a LAN, not the PSTN interface Part 68 registration covers.
   - This research did **not** establish whether, or how, Part 68 HAC labeling applies to a SIP-only phone.
   - So for a SIP phone, compliance cannot be assumed from the rules. It needs the manufacturer's written declaration plus our own test.
2. **Choice.** Amplified, high-volume, telecoil-coupled, visual-ring phones for hearing loss are mostly analog products. This is a market observation, not a cited fact; verify it for each candidate.
3. **Architecture fit.** The warm-line and dial plan already live in the ATA and Asterisk (D6/D8). The handset stays a simple, replaceable part.

**When to prefer a native SIP HAC phone:**
- the facility already standardises on one SIP phone model;
- the room needs features an ATA cannot carry, such as a display with caller name or message-waiting on screen;
- the vendor supplies written §68.316 and TIA-4965 compliance evidence and the phone passes HT-01..HT-08.

**The ATA itself has no hearing-aid role.** It must not degrade audio:
- G.711 µ-law, per D6;
- no aggressive compression;
- correct ring voltage and cadence for the chosen visual indicator (H-7, H-13).

### 1.4 Wireless note (only relevant if a cordless or cellular handset is ever chosen)

Wireless handsets are certified against **ANSI C63.19-2019** (acoustic coupling and telecoil coupling) with volume control per **ANSI/TIA-5050-2018** [F6].

For handset models certified **on or after 2026-12-14**, the rule requires:
- acoustic coupling;
- volume control;
- **either** telecoil coupling **or Bluetooth coupling "as a replacement for or in addition to"** telecoil [F6].

**Consequence:** a newly certified wireless phone may have **no telecoil coupling at all**. If a wireless handset is ever considered, telecoil coupling must be a separately verified MUST. Cordless phones also fall under the wireline §68.4 HAC rule [F1].

---

## 2. Personal phone + Bluetooth hearing aids — architecture rule

### 2.1 Rules

- **R-1 — The resident's personal phone is the Bluetooth owner of their hearing aids.**
  - CAOSCare does **not** pair the central server, the Voice PE or any room device directly with a resident's hearing aids.
  - Changing this rule needs new, documented evidence of a very strong reason, plus a test showing the resident's own phone connection is not disturbed.
  - Why: architecture doc §6.1 — coordinated binaural sets, connection-slot limits, OS-owned MFi/ASHA pairing, and fitting liability.
- **R-2 — The room microphone is the default input:** Voice PE → Aria. This is independent of any hearing device.
- **R-3 — Personal output path (optional, per resident):** Aria → CAOSCare companion surface on the resident's phone → OS audio route → paired hearing aids. The OS decides the route; CAOSCare does not force it.
- **R-4 — Fallback:** if Bluetooth or the phone is unavailable, the room microphone and room speaker are used.
  - A reply is committed before it is played.
  - If the phone does not confirm playback (no ack, heartbeat lost, or route changed to the phone's own speaker), the same reply is replayed on the Voice PE speaker and the fallback is recorded.
  - No request depends on personal audio.
- **R-5 — One playback path per call.** While a handset call is active (or its speakerphone is on), the Voice PE must not start an Aria conversation or wake from call audio.
  - Reason: same principle as `ROOM_AUDIO_ARCHITECTURE.md` (uncoordinated playback paths defeat AEC).
  - This is a **software requirement** to verify in HT-09. It is not built.
- **R-6 — CAOSCare never changes hearing-aid programs, presets or volume.**

### 2.2 Flow

```
Resident speaks ──► Voice PE mic ──► central HA/CAOSCare ──► Aria reply (committed)
                                                            │
             personal output enabled + phone online + route ok?
                    │yes                                   │no
                    ▼                                      ▼
   phone companion ─► OS route ─► hearing aids        Voice PE speaker
        │ ack within T_ack?
        └─no─► replay on Voice PE speaker (record fallback)
```

### 2.3 Not built — required before any of R-3/R-4 can be tested

- A phone-side CAOSCare audio surface with background-audio capability (architecture doc §11.1).
- The output decision function and fallback replay.
- Route reporting.
- The R-5 handset/Voice PE interlock.

---

## 3. Hearing-device capability classes

**Rule:** classify by the *verified* path a CAOSCare surface can use. **Never infer microphone availability from the fact that the aid contains microphones** — every hearing aid does.

| Class | Meaning | Typical technology (documented) | What CAOSCare may use |
|---|---|---|---|
| **A — Output streaming only** | Phone audio streams *to* the aids; the phone's own microphone carries the voice | ASHA: "There is no audio backlink…the central microphones are used for voice input" [G1]. MFi on a phone below bidirectional requirements (before iPhone 11 / iOS 15.2) [A2]. | Room mic or phone mic in; aids out (Mode B) |
| **B — Hands-free call microphone** | The aid's microphone works **for the phone's own calls** (OS call path). App access is not established. | Bidirectional MFi, iPhone 11+ / iOS 15.2+ [A2]. Bluetooth Classic HFP aids [M1][M5]. LE Audio aids on a supporting phone (call use [G3]). | Same as A. Personal calls on the resident's phone may be hands-free. **Aria must not assume the aid mic.** |
| **C — App-accessible microphone** | A CAOSCare phone surface has been **shown by test** to capture from the aid's microphone | Candidate: LE Audio aid + LE Audio Android phone via `setCommunicationDevice()` [G3][G4]. Possibly a Classic HFP aid used as a headset (untested). iOS: no documented path [A5]; unproven. | Mode C, only after HA-05 / PA-03 passes for that exact aid + firmware + phone + OS |
| **D — No Bluetooth** | Traditional aid, or Bluetooth not paired / not used | Telecoil aids, non-wireless aids | Room mode; HAC handset via telecoil if the aid has a T-coil (telecoil presence is a separate fact) |

**Classification procedure:**
1. Start from the manufacturer's documentation for the exact model and firmware → provisional A, B or D.
2. **C is only ever assigned by a passed test.**
3. Re-test after any change of OS major version, phone, aid or aid firmware (profile field `last_reviewed_at`, architecture doc §8).

---

## 4. Physical acceptance matrix (future — none run)

Each test records the exact models, firmware and OS. For a phone test, it also records the route the platform reports (iOS `AVAudioSession.currentRoute` port type; Android communication device / `AudioDeviceInfo` type).

**Global pass rule:**
- every Aria reply is heard on some endpoint;
- every request has a receipt;
- every fallback is recorded;
- no test changes hearing-aid settings.

### 4.1 Personal-device tests

| ID | Scenario | Setup | Steps | Pass |
|---|---|---|---|---|
| PA-01 | iPhone + compatible aids | MFi aids on an iPhone; class A or B | Voice PE input; output preference = aids | Reply heard in the aids; Voice PE speaker silent; route `bluetoothLE`; ack received |
| PA-02 | Android ASHA, output-only | ASHA aids, Android phone | As PA-01; then request aid-mic input | Reply in the aids (route `TYPE_HEARING_AID`); system never claims the aid mic; input stays Voice PE or phone mic |
| PA-03 | Android LE Audio bidirectional | LE Audio aids + LE Audio phone on that manufacturer's compatibility list | Phone surface; input preference = aid; phone mic covered | Transcript produced from aid mic; intelligibility ≥ phone-mic baseline → **only then** record class C |
| PA-04 | Traditional non-Bluetooth aids | Class D aids | Normal room conversation at the usual seating distance | Room mode works; nothing attempts personal audio |
| PA-05 | Both aids connected | Bilateral set, PA-01/02 setup | Reply streamed | Audio in both ears; route reported once (not duplicated) |
| PA-06 | One aid disconnected | Bilateral set | Remove battery from one aid mid-reply | Audio continues in the remaining aid (ASHA documents mono mix [G1]; others measured); conversation continues; no false "delivered to both" |
| PA-07 | Bluetooth loss mid-conversation | PA-01/02 setup | Turn Bluetooth off mid-reply; also walk out of range | Reply completed or replayed on the Voice PE speaker; next turn works; fallback receipt |
| PA-08 | Phone battery dead / phone off | Personal output configured | Power the phone off; then kill the app | Heartbeat loss → room mode within one turn; nothing queued silently for the phone |
| PA-09 | Room speaker fallback, by choice | Personal-capable resident sets output = room | Normal conversation | Nothing sent to the phone |

### 4.2 Handset tests

| ID | Scenario | Steps | Pass |
|---|---|---|---|
| HT-01 | Label & documents | Inspect the unit; collect spec sheets | "HAC" permanently marked; §68.316 + TIA-4965 declaration on file (H-1, H-2) |
| HT-02 | Acoustic use, aid in M mode | Resident or tester with aids in microphone mode, max volume | Speech intelligible; no squeal (feedback) with the receiver at the ear |
| HT-03 | Telecoil coupling | Aid in T or MT mode, receiver held at the aid | Clear call audio, no hum or buzz; switch to T works (H-5) |
| HT-04 | Amplification + reset | Set max amplification; hang up; lift again | Measured or observed boost; gain back to ≤24 dB after on-hook if it was above 24 dB (H-3) |
| HT-05 | **Front-desk call** | Lift → dial 0 → ext 200 | Rings front desk; two-way audio intelligible through telecoil and acoustic use; call receipt |
| HT-06 | Ring & visual ring via ATA | Call the room extension | Audible ring at a high setting; visual indicator flashes on the ATA ring signal (H-7, H-13) |
| HT-07 | Power loss | Unplug the phone's AC adapter (not the ATA) | Record actual behaviour: dial tone? audio? amplification? (H-11 — any result is recorded; failure is a planning input, not a hidden pass) |
| HT-08 | Warm-line + immediate dial | Lift and wait → Aria; lift and dial 0 / 933 test number | Warm-line reaches Aria; 0 and 911-path dial immediately (911 via provider test number only) |
| HT-09 | Handset vs Voice PE interlock (R-5) | During an active handset call, use speakerphone; say "Hey Aria" from the far end and in the room | Voice PE does not start a conversation or wake from call audio; call audio is not transcribed into Aria |
| HT-10 | **Family call** (Aria-initiated) | Aria places a call to a family member | **(a)** to the room handset: answerable and intelligible via telecoil. **(b)** if the resident chooses their mobile: OS hearing-device call routing used; mic source recorded. Call receipt in both cases |

### 4.3 Mapping to architecture doc §9

| This doc | Architecture doc |
|---|---|
| PA-01 | HA-03 |
| PA-02 | HA-04, HA-06 |
| PA-03 | HA-05 |
| PA-04 | HA-02 |
| PA-06 | HA-09 |
| PA-07 | HA-07, HA-14 |
| PA-08 | HA-08 |
| PA-09 | HA-11 |
| HT-10 | HA-10 |

HA-01 (no aids) and HA-12/13 (dual output, program switch) remain as written there.

---

## 5. Procurement gate (one page)

Mark each line **PASS / FAIL / UNKNOWN / N/A**.
- An item is PASS only with evidence: a label photo, a spec sheet/declaration, or a test ID.
- **UNKNOWN stays UNKNOWN.** It is never rounded to PASS.
- Any MUST that is FAIL or UNKNOWN blocks purchase, and later blocks acceptance.

**A. Room handset** — model: ______ firmware/rev: ______ evaluator/date: ______

| # | Check | Level | Result | Evidence |
|---|---|---|---|---|
| A1 | Permanent "HAC" mark on unit (§68.300(b)) | MUST | | |
| A2 | Manufacturer declares §68.316 (RS-504 magnetic field) compliance | MUST | | |
| A3 | Volume control per §68.317(h) / TIA-4965 (18–24 dB) declared | MUST | | |
| A4 | If >24 dB: auto-reset on hang-up | MUST (if >24 dB) | | |
| A5 | Max amplification value (dB): ____ ≥30 dB | SHOULD | | |
| A6 | Tone / frequency adjustment | SHOULD | | |
| A7 | Visual ring indicator; works with the selected ATA's ring signal | SHOULD | | |
| A8 | Ringer volume high / adjustable | SHOULD | | |
| A9 | Speakerphone | SHOULD | | |
| A10 | Large, high-contrast buttons; memory keys | SHOULD | | |
| A11 | Power-loss behaviour documented | MUST (known) | | |
| A12 | REN within ATA FXS ringer load | MUST | | |
| A13 | Corded (not cellular). If cordless/wireless: telecoil coupling separately verified (§1.4) | MUST | | |
| A14 | Neckloop / 3.5 mm out | OPTIONAL | | |
| A15 | Telecoil test passed (HT-03) | MUST at acceptance | | |

**B. ATA** — model: ______

| # | Check | Level | Result | Evidence |
|---|---|---|---|---|
| B1 | Warm-line + immediate-dial plan (0 / 911 / 9911 / 933) | MUST | | |
| B2 | G.711 µ-law; RFC 2833/4733 DTMF | MUST | | |
| B3 | Supported ringer load (REN) and ring voltage stated | MUST | | |

**C. Personal hearing device (per resident, recorded — not purchased by CAOSCare)** — make/model/firmware: ______ phone/OS: ______

| # | Check | Result | Evidence |
|---|---|---|---|
| C1 | Manufacturer documents streaming for this exact phone + OS | | |
| C2 | Provisional class (A/B/D) from manufacturer documentation | | |
| C3 | Telecoil present (for HAC handset use) | | |
| C4 | PA-01/PA-02 output test passed | | |
| C5 | Class C claimed? Only if PA-03 passed → test ID | | |
| C6 | Resident consents to personal-audio setup; no medical data recorded | | |

**Not a pass criterion anywhere:**
- a brand name;
- "hearing aid compatible" marketing text without the label or declaration;
- "made for iPhone" without the bidirectional requirements (iPhone 11+ / iOS 15.2+, a brand on Apple's list [A2]) **and** a test.

---

## 6. New sources (accessed 2026-10-04; read via the eCFR renderer API)

- [F1] 47 CFR §68.4 Hearing aid-compatible telephones — https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-68/subpart-A/section-68.4
- [F2] 47 CFR §68.6 Telephones with volume control — https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-68/subpart-A/section-68.6
- [F3] 47 CFR §68.316 Hearing aid compatibility: technical requirements (EIA RS-504 text incorporated; §§4.2–4.4) — https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-68/subpart-D/section-68.316
- [F4] 47 CFR §68.317 Hearing aid compatibility volume control: technical standards, paragraph (h) — https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-68/subpart-D/section-68.317
- [F5] 47 CFR §68.300 Labeling requirements, paragraph (b) — https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-68/subpart-D/section-68.300
- [F6] 47 CFR §20.19 Hearing aid-compatible mobile handsets (definitions: acoustic, telecoil, Bluetooth coupling; ANSI C63.19-2019; TIA-5050-2018; requirements before / on-or-after 2026-12-14) — https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-20/section-20.19

The FCC consumer guide (fcc.gov/consumers/guides/hearing-aid-compatibility-wireline-and-wireless-telephones) returned HTTP 403 to automated fetch, so the regulation text above was used instead.

**Not established by this research** (left UNKNOWN on purpose):
- whether Part 68 HAC labeling obligations apply to SIP-only phones;
- REN and ring-voltage values for any specific ATA or phone;
- any specific phone model's actual magnetic field or gain.
