# Owner instruction intake (RQ-042)

Michael posts instructions as GitHub issue comments (issue #117 and any open issue labelled `owner-instruction`). A running Claude CLI session is **not woken** by a comment. This intake closes that gap with a small, bounded poller on the coordinator host. Code: `scripts/owner_intake/`.

## How it works
- `poll.py` runs from a systemd `--user` timer (`scripts/owner_intake/systemd/`, every 5 min; **not installed by the repo** - install: copy to `~/.config/systemd/user/`, `systemctl --user daemon-reload && systemctl --user enable --now caos-owner-intake.timer`).
- Per run: one `gh api` call for the label list, then per watched issue one comments call (plus one issue-body call the first time). Hard caps: `max_gh_calls_per_run` (10) and `max_items_per_run` (50), from `scripts/owner_intake/config.json` (override file: `CAOS_INTAKE_CONFIG`). No `--paginate`. No model calls, no new secrets: it uses the existing `gh` login.
- State dir `~/.local/state/caoscare-intake/` (`CAOS_INTAKE_DIR`):
  - `inbox.jsonl` - append-only, one line per issue body / comment: `item_id` (`gh:<repo>#<issue>:comment:<id>` or `:body`), `author`, `association`, `created_at`, `sha256` of the body, `body`, `first_seen`, `source`, `status` (ingestion status `NEW`, or `n/a`).
  - `cursor.json` - per issue last comment id / `created_at` (used as `since=`), poster rate-limit time, backoff.
  - `receipts.jsonl` - one receipt per event: `ingested`, `status`, `nudge`, `poll_error` (item_id, time, poller version, host, result).
- Idempotent: items dedupe by `item_id`; the cursor moves only past items already written to disk. An edited comment keeps its first-seen text (hash recorded).

## Who counts as the owner
Only `author_association` OWNER / MEMBER / COLLABORATOR is actionable (`source=owner`); anyone else is stored as `untrusted` and never actionable. The coordinator posts as the **same GitHub login** as Michael, so every coordinator comment must start with the marker line `<!-- caos:coordinator -->`; such items are stored `source=coordinator`, status `n/a`, never actionable. The `status --post` command adds the marker automatically.

## Commands
- `poll.py` - one poll. `--auto-ack` posts ONE short ACK comment per run covering all new items (default off).
- `poll.py --replay` - owner items whose latest status is not DONE (use after a restart).
- `poll.py show <item_id>` - print an item.
- `poll.py status <item_id> ACK|WORKING|BLOCKED|DONE [--note T] [--post]` - append a status receipt; with `--post`, one GitHub comment (marker included). The same status is never repeated; a `--post` is retried only if the earlier post did not succeed. Posts are spaced by `min_post_interval_seconds` (20 s).
- Current item status = the latest `status` receipt (the inbox line is never rewritten).

## Delivery semantics
"Posted" (Michael wrote a comment) is not "delivered". Delivery is recorded in stages: `ingested` (on disk, within 5 min of the post) -> optional `nudge` -> `ACK` (the coordinator actually read it) -> WORKING / BLOCKED / DONE. Only an `ACK` receipt from a running coordinator proves it was seen.
Optional nudge: set `CAOS_INTAKE_NUDGE_TMUX=<session:window>` (default off) and the poller sends one line to that pane per new owner item, once, never if the pane is missing (`nudge` receipt says `sent` / `pane_not_found` / `failed`).

## Timing and failure modes
- Next check happens at the next timer tick (<= 5 min, plus poll time).
- `gh` failure or rate limit: cursor unchanged, `poll_error` receipt, exponential backoff 5 min -> 1 h (during backoff the run makes no gh call); success clears it.
- Two overlapping runs: a file lock makes the second exit.
- Budget: ~2-3 gh calls per 5 min with the default watch list; zero provider spend.
- Not covered: a coordinator that never runs `--replay`/`show`; a down host; comments deleted before ingestion.

## Consuming from another system (Desktop-Agent / mission control)
A search of the repo, `~/CAOSCARE-AGENT-CONTROL*` and `~/bin` found **no existing inbox file convention** (the agent-control mock adapter has an in-memory per-binding inbox only). So the schema above is the documented one: read `inbox.jsonl` for items and `receipts.jsonl` (latest `status` per `item_id`) for state; write status back only through `poll.py status` so receipts stay in one place.

## Tests
`~/CAOSCARE-INTEGRATION/backend/.venv/bin/python3 -m pytest scripts/owner_intake` (system python has no pytest). A stub `gh` executable is used; no network.
