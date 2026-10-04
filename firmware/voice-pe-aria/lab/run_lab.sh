#!/usr/bin/env bash
# Unattended Phase 2 pipeline (identical conditions). Logs in ~/caoscare-firmware-work/lab_logs.
# Order: shared negatives -> per-candidate positives -> for each candidate: train, then evaluate
# (evaluation waits for run_eval_gen.sh to finish the held-out clips) -> report.
set -u
LAB=$(cd "$(dirname "$0")" && pwd)
PY=$HOME/caoscare-firmware-work/venv-mww/bin/python
LOGS=$HOME/caoscare-firmware-work/lab_logs
mkdir -p "$LOGS"
cd "$LAB" || exit 1
$PY gen_lab.py negatives > "$LOGS/gen_negatives.log" 2>&1 || exit 1
$PY gen_lab.py positives > "$LOGS/gen_positives.log" 2>&1 || exit 1
for s in $($PY -c "import json;print(' '.join(c['slug'] for c in json.load(open('trained_candidates.json'))))"); do
  if [ ! -f "$HOME/caoscare-firmware-work/runs/lab/$s/trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite" ]; then
    $PY train_lab.py "$s" > "$LOGS/train_$s.log" 2>&1 || echo "$(date -Is) TRAIN FAILED $s" >> "$LOGS/pipeline.log"
  fi
  while [ ! -f "$LOGS/gen_eval.done" ]; do sleep 30; done
  if [ ! -f "$HOME/caoscare-firmware-work/runs/lab/$s/lab_eval.json" ]; then
    $PY eval_lab.py "$s" > "$LOGS/eval_$s.log" 2>&1 || echo "$(date -Is) EVAL FAILED $s" >> "$LOGS/pipeline.log"
  fi
  echo "$(date -Is) done $s" >> "$LOGS/pipeline.log"
done
$PY report_lab.py > "$LOGS/report.log" 2>&1
echo "$(date -Is) PIPELINE COMPLETE" >> "$LOGS/pipeline.log"
