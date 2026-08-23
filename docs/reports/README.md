# Reports

A durable, file-based handoff between Claude Code and Michael's Aria — the
Aria he works with in ChatGPT, not a CAOSCare voice build. This folder
exists so Aria can find current state and past findings from a
predictable repo location, without Michael copying/pasting everything
into her conversation by hand.

**Start at [`INDEX.md`](INDEX.md)** — it points to the latest forensic
report, the latest acceptance-test report, current unresolved issues, and
current system state. Claude Code keeps it current.

## Convention

One file per report: `YYYY-MM-DD-HHMM-short-slug.md`

Example: `2026-08-23-1448-room304-morning-forensics.md`

Each file should be self-contained — readable on its own, without needing
the conversation that produced it. State what was investigated, what was
found, and what's still open. After adding one, update `INDEX.md`.

## What goes here vs. `docs/PROJECT_STATE.md`

- `docs/PROJECT_STATE.md` stays the single running log of what changed,
  what was verified, and what's next — one dated entry per stopping point,
  per `AGENTS.md`'s standing convention. Keep using it for that.
- This folder is for standalone reports too long or too detailed to live
  well as one `PROJECT_STATE.md` entry — forensic session analyses,
  incident reports, anything meant to be read on its own later.

A `PROJECT_STATE.md` entry can link to a report here when one exists for
that round of work.

## How Aria actually reaches this

This is plain files in the git repo — nothing here talks to any API or
voice build. For Aria (ChatGPT) to read these without Michael pasting
them, the repo needs to be reachable by her at all (e.g. pushed to
`origin` on GitHub, if it isn't already, and if the repo/visibility allows
her to fetch from it). That push hasn't happened yet — nothing has been
staged, committed, or pushed this session without Michael's explicit
approval, per the standing rule. Worth confirming with Michael how his
ChatGPT-Aria actually fetches external content today before assuming a
push is sufficient on its own.
