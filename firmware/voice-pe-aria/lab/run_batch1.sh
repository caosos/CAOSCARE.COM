#!/usr/bin/env bash
# Round 5 acoustic batch 1 (8 funnel phrases). Identical procedure to the corrected 26-model lab
# (772e216 + deterministic per-clip seed): same generator settings, shared negatives, evaluation
# conditions, negative/ambient sets and scoring. One retry with the identical configuration on
# failure, then FAILED is logged; nothing is dropped. Sequential (one heavy job at a time).
set -u
LAB=$(cd "$(dirname "$0")" && pwd)
PY=$HOME/caoscare-firmware-work/venv-mww/bin/python
W=$HOME/caoscare-firmware-work
LOGS=$W/lab_logs
LOG=$LOGS/batch1_pipeline.log
TFL=trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite
cd "$LAB" || exit 1
step() {   # step <name> <cmd...>  - one retry with identical configuration
  local name=$1; shift
  "$@" > "$LOGS/batch1_$name.log" 2>&1 && return 0
  cp "$LOGS/batch1_$name.log" "$LOGS/failures/batch1_$name.attempt1.log"
  echo "$(date -Is) RETRY $name" >> "$LOG"
  "$@" > "$LOGS/batch1_$name.log" 2>&1 && return 0
  echo "$(date -Is) FAILED $name" >> "$LOG"; return 1
}
echo "$(date -Is) START" >> "$LOG"
step gen_positives $PY gen_lab.py positives batch1
step gen_eval $PY gen_lab.py eval batch1
echo "$(date -Is) GENERATION DONE" >> "$LOG"
for s in $($PY -c "from lab_common import load_batch_candidates as L; print(' '.join(c['slug'] for c in L()))"); do
  [ -f "$W/runs/lab/$s/$TFL" ] || step "train_$s" $PY train_lab.py "$s"
  [ -f "$W/runs/lab/$s/$TFL" ] && { [ -f "$W/runs/lab/$s/lab_eval.json" ] || step "eval_$s" $PY eval_lab.py "$s"; }
  [ -f "$W/runs/lab/$s/$TFL" ] && { [ -f "$W/runs/lab/$s/lab_eval_supp_cross.json" ] || step "cross_$s" $PY eval_lab.py "$s" --cross-supplemental; }
  echo "$(date -Is) done $s" >> "$LOG"
done
echo "$(date -Is) BATCH1 COMPLETE" >> "$LOG"
