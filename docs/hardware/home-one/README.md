# Home One: design concepts and parts plans (NOT BUILT)

**Status: concept only.** No Home One unit has been built, bought, wired or
tested. Nothing in this folder describes a working device or a proven
capability. Issue #165 tracks Home One; it is a feasibility item. The proven
Room 214 endpoint is still the eMeet speakerphone with the local "Hey Aria"
listener on the central EliteDesk (see `docs/CAOSCARE_PRODUCT_BASELINE.md` §2).

Name: **Home One** (owner, 2026-10-23). The older blueprint says "CAOSCare One"
and older mockups say "CareOne". These are superseded names for the same
concept.

Michael supplied these files on 2026-10-23 from his laptop's
`~/Downloads/CAOScare.com/photos`. They were resized to JPEG; the content is unchanged.

| File | What it is |
|---|---|
| `home-one-concept-render.jpg` | Design render: a horizontal speaker with a handle, plus an upright version. Captioned "Design concept — not a built or tested product". This render is also shown on the public home page, labelled as a concept. |
| `home-one-concept-blueprint.jpg` | Design render: front view, cutaway and "how it all works together" (uses the old name "CAOSCare One"). It shows the intended direction: far-field microphones, a speaker, radios (Wi-Fi, Bluetooth, Zigbee, Z-Wave, Thread, IR, SDR), a Raspberry Pi 5 and backup battery. The marketing lines in it are aspirations, not commitments: "five years of updates", "no mandatory subscription". |
| `parts-candidates-current-core-2026-10-23.jpg` | Parts candidates: Pi 5 4 GB, Active Cooler, Seeed XVF3800 4-mic array, Sony 4 Ω driver, Bioenno 240 Wh LiFePO4 pack, Mini-box OpenUPS, 52Pi power converter, optional USB-C PD sink, Mean Well 90 W / 24 V adapter. It is marked "power chain and wiring not validated · not a ready-to-build kit". |
| `parts-candidates-lightweight-2026-10-23.jpg` | Lighter option: Pi 5 4 GB, XVF3800, Sony driver, PiPower5, Tenergy 38 Wh pack, Active Cooler; planning budget $494.08 before tax and shipping. It is marked "Electrical hold — not order ready". The one-hour runtime and 2–3 lb weight are modelled, not measured. |

The parts sheets cite `parts_catalog/manifest.json` (sources and engineering
caveats). That file is **not in this repository yet**. Treat the prices and
part numbers as reference quotes from 2026-10-23, not a bill of materials.

Before anything here is called built, it needs:

- an owner decision on the parts;
- a validated power chain;
- a physical build;
- the same acceptance a room endpoint gets: wake, conversation, goodbye, TV/room control, recovery after power loss;
- receipts for each of the above.
