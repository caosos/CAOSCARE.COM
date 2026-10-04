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

Room architecture (Michael, 2026-10-03; Product Baseline §2): one central
community EliteDesk runs Home Assistant and CAOSCare; each apartment uses a
Home Assistant Voice Preview Edition as the Aria room voice endpoint over
Wi-Fi. No EliteDesk in each apartment; no eMeet in the standard room; test
the Voice PE microphones in a real apartment before adding another audio
endpoint. SIP/front-desk calling stays a separate handset/telephony function
unless later testing establishes another accepted architecture. Assistant:
Aria; primary wake phrase "Hey Aria", secondary test candidate "Aria".
Resident rooms are not tablet-based. *Superseded, history only: "room node
behind the TV + eMeet audio + TV" per apartment.* File size/modularity target: implementation
files ~300-400 lines, ~400 a split signal not a hard wall — see `AGENTS.md`
"Change discipline" for the canonical rule (do not restate it here).

Do not redesign established architecture without first identifying the
existing design and explaining why a change is necessary.
