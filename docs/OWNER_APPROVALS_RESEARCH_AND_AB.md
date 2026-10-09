# One consolidated approval: live research + model A/B (replaces asking sequentially)

Everything below is **built, tested offline and merged**; nothing is enabled and no paid call has been made. Each line is independent: approve any subset by quoting its letter. Reply on issue #117 (the coordinator reads it through Desktop-Agent).

| | What you are approving | Default / recommendation | Cost bound | If you decline |
|---|---|---|---|---|
| **A** | **Choose the research model** (`OPENAI_RESEARCH_MODEL`). No default exists in code. Option 1 (recommended): authorize the coordinator to pick the cheapest model the provider's current docs list as supporting `web_search`, record the name and its source in `docs/RESEARCH_PROVIDER.md` before any call. Option 2: you name the model. | Option 1 | none by itself | research stays non-live; Aria says she cannot look things up |
| **B** | **ONE smoke call** of the new research path on an isolated stack (one question with a known current answer; verify `live=true`, citations present, receipt written). | approve | one search call plus tokens: under $0.50 (stop if the provider's usage shows more) | A and C stay unverified |
| **C** | **Live switch of research on Room 214**: set `CAOSCARE_RESEARCH_PROVIDER=openai_web_search` and the model, restart the backend only with no live Aria lease. Guards already merged: live-session required (or owner login), 6 lookups per minute per room. Rollback: set the provider to `none`, restart. | approve only after B passes | ongoing, per resident lookup (low frequency expected) | |
| **D** | **Model A/B** (`gpt-realtime` vs `gpt-realtime-2.1-mini`), isolated stack, stage 1 scripted typed runs + stage 2 one attended voice session per model. Harness is merged and refuses to run without this approval. | approve | up to $5 total | Room 214 keeps `gpt-realtime` |
| **E** | **Switching Room 214's voice model** after D passes every gate (one env line, restart with no live lease, rollback = remove the line). | decide after D | n/a | |

**One-line approval you can paste (covers A option 1, B, D):**
> AUTHORIZE: research model chosen by the coordinator from provider docs (A); one research smoke call, up to $0.50 (B); model A/B, isolated stack only, up to $5 total (D). Total cap $5.50. Do NOT change Room 214 until I approve C and E separately.

Not covered by anything above: deployment to Linode, new vendors or credentials, wake-word settings (threshold 0.05 / score 1.5 stay), audio recording.
