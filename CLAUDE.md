# CAOSCare Agent Onboarding

You are working on CAOSCare. This is not a generic AI application.

Boot order (canonical full sequence in AGENTS.md / the Product Baseline §9):

@AGENTS.md
@docs/CAOSCARE_PRODUCT_BASELINE.md
@docs/PROJECT_STATE.md
@docs/REPO_MAP.md

Then, for architecture, prompt, memory, tool, voice, resident, or device
work, also read:

@docs/ENGINEERING_CONTRACT.md
@docs/CAOS_THESIS.md
@docs/CAOSCARE_BLUEPRINT.md
@docs/ARIA_CONTRACT.md

(`CAOS_THESIS`, `CAOSCARE_BLUEPRINT`, and `ARIA_CONTRACT` are still
placeholders — do not treat their absence of content as architecture.)

Before implementation work, also read docs/CURRENT_NODE_STATUS.md and
inspect the actual machine/repository state. Status documents are
snapshots, not proof that the current runtime still matches them.

Room architecture (owner direction 2026-10-14/15; Product Baseline §2): one
central community EliteDesk runs Home Assistant and CAOSCare; the proven room
endpoint is Room 214's eMeet + local "Hey Aria" listener; the Voice PE was
rejected on 2026-10-14; future appliance direction is CAOSCare Home One (#165,
not built). SIP/front-desk calling stays a separate handset/telephony function
unless later testing establishes another accepted architecture. Assistant:
Aria; primary wake phrase "Hey Aria", secondary test candidate "Aria".
Resident rooms are not tablet-based. *Superseded, history only: Voice PE as the
per-apartment endpoint (2026-10-03 → 2026-10-14); "room node behind the TV +
eMeet audio + TV" per apartment.* Current status/runtime: the header of
`docs/PROJECT_STATE.md`. File size/modularity target: implementation
files ~300-400 lines, ~400 a split signal not a hard wall — see `AGENTS.md`
"Change discipline" for the canonical rule (do not restate it here).

Do not redesign established architecture without first identifying the
existing design and explaining why a change is necessary.
