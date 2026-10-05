"""Fetch the TV-dialogue-style hard-negative source for the Okay Sequoia method A/B (2026-10-04).
MLCommons/peoples_speech, config 'clean', validation shards 00000-00001, pinned revision.
Licence per dataset card: CC-BY / CC-BY-SA family. Completely separate from the evaluation
TV-dialogue stream (LibriSpeech test-clean)."""
from huggingface_hub import hf_hub_download
REV = "f10597c5d3d3a63f8b6827701297c3afdf178272"
for f in ("clean/validation-00000-of-00005.parquet", "clean/validation-00001-of-00005.parquet"):
    p = hf_hub_download("MLCommons/peoples_speech", f, repo_type="dataset", revision=REV, local_dir=".")
    print(p, flush=True)
