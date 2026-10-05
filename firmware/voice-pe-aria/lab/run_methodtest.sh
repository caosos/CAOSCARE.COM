#!/usr/bin/env bash
# Training-method A/B (2026-10-04): one model, okay_sequoia_tvneg. Plan fixed in
# research/wake-phrase-funnel/method_test/PLAN_RECEIPT.md. One identical retry on failure.
set -u
LAB=$(cd "$(dirname "$0")" && pwd)
PY=$HOME/caoscare-firmware-work/venv-mww/bin/python
W=$HOME/caoscare-firmware-work
HN=$W/data/hardneg_peoples_speech
LOGS=$W/lab_logs; LOG=$LOGS/methodtest_pipeline.log
S=okay_sequoia_tvneg
cd "$LAB" || exit 1
step() { local n=$1; shift
  "$@" > "$LOGS/methodtest_$n.log" 2>&1 && return 0
  cp "$LOGS/methodtest_$n.log" "$LOGS/failures/methodtest_$n.attempt1.log"; echo "$(date -Is) RETRY $n" >> "$LOG"
  "$@" > "$LOGS/methodtest_$n.log" 2>&1 && return 0
  echo "$(date -Is) FAILED $n" >> "$LOG"; return 1; }
echo "$(date -Is) START" >> "$LOG"
for f in validation-00000-of-00005 validation-00001-of-00005; do   # both pinned shards must be present
  [ -f "$HN/clean/$f.parquet" ] || { echo "$(date -Is) FAILED missing shard $f" >> "$LOG"; exit 1; }
done
[ -f "$HN/features/testing/wakeword_mmap" ] || [ -d "$HN/features/testing/wakeword_mmap" ] || step prep $PY "$HN/prep.py" || exit 1
echo "$(date -Is) HARD NEGATIVES READY" >> "$LOG"
step train $PY train_lab.py $S || exit 1
step eval $PY eval_lab.py $S
step cross $PY eval_lab.py $S --cross-supplemental
echo "$(date -Is) METHODTEST COMPLETE" >> "$LOG"
