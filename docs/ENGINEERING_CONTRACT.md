# Engineering Contract — placeholder

**Not yet written.** This document is meant to define how agents are expected to work specifically within CAOSCare — the project-specific complement to the universal engineering principles in the global `~/.claude/CLAUDE.md` (understand before changing, one source of truth, verify the exact path the user uses, documentation describes reality, etc.).

Meant to cover things specific to this repository: the required-reading order and when it applies, the code-size discipline already stated in `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md` (200-line soft target, 400-line hard cap), how/when to update `docs/PROJECT_STATE.md` and `docs/CURRENT_NODE_STATUS.md`, how contradictions between docs and running code should be surfaced and resolved, and any CAOSCare-specific SOPs for recurring operations (deploying, restarting services, testing voice paths, etc.).

To be built collaboratively with Michael. **Do not invent this document's contents.**

---

## Code file size (Michael-directed, 2026-08-21)

The rest of this document is still unwritten — this section is an explicit rule Michael gave directly, not an agent inference, recorded here so it isn't lost before the full contract exists.

Handwritten production code files must not exceed 300 lines unless Michael explicitly approves an exception.

- Aim below 300 lines.
- Split by clear domain or responsibility, never arbitrary line chopping.
- Do not create God files.
- Do not launch a broad refactor solely to shorten an untouched legacy file that is already over the cap.
- If modifying an existing code file already above 300 lines, do not make it larger — extract the responsibility being changed when practical.
- Before finishing any coding task, report the line counts of every created or materially modified production-code file.

Documentation, informational files, reports, generated files, static data, lockfiles, and necessary configuration files are exempt.

This replaces the prior 400-line hard cap recorded in `AGENTS.md`.
