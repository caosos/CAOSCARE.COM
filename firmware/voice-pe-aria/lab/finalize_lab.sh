#!/usr/bin/env bash
# Overnight completion (Michael, 2026-10-04): runs after run_lab.sh and run_supplemental.sh.
# For each of the 26 candidates: if training / evaluation / cross-check is missing, preserve the
# failure log, retry ONCE with the identical configuration, else mark FAILED with evidence.
# Then rebuild report, recommendation and provenance (with per-model status and timings).
set -u
LAB=$(cd "$(dirname "$0")" && pwd)
PY=$HOME/caoscare-firmware-work/venv-mww/bin/python
W=$HOME/caoscare-firmware-work
LOGS=$W/lab_logs
FAIL=$LOGS/failures
mkdir -p "$FAIL"
cd "$LAB" || exit 1
TFL=trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite
until grep -q "SUPPLEMENTAL COMPLETE" "$LOGS/pipeline.log" 2>/dev/null; do sleep 120; done
slugs() { $PY -c "import json;print(' '.join(c['slug'] for c in json.load(open('$1'))))"; }
retry() {   # retry <kind> <slug> <cmd...>
  local kind=$1 s=$2; shift 2
  [ -f "$LOGS/${kind}_$s.log" ] && cp "$LOGS/${kind}_$s.log" "$FAIL/${kind}_$s.attempt1.log"
  echo "$(date -Is) RETRY $kind $s (identical configuration)" >> "$LOGS/pipeline.log"
  "$@" > "$LOGS/${kind}_$s.retry.log" 2>&1 || {
    cp "$LOGS/${kind}_$s.retry.log" "$FAIL/${kind}_$s.attempt2.log"
    echo "$(date -Is) FAILED_FINAL $kind $s" >> "$LOGS/pipeline.log"; }
}
for s in $(slugs trained_candidates.json) $(slugs supplemental_candidates.json); do
  if [ ! -f "$W/runs/lab/$s/$TFL" ]; then
    retry train "$s" $PY train_lab.py "$s"
  fi
  if [ -f "$W/runs/lab/$s/$TFL" ] && [ ! -f "$W/runs/lab/$s/lab_eval.json" ]; then
    retry eval "$s" $PY eval_lab.py "$s"
  fi
  if [ -f "$W/runs/lab/$s/$TFL" ] && [ ! -f "$W/runs/lab/$s/lab_eval_supp_cross.json" ]; then
    retry cross "$s" $PY eval_lab.py "$s" --cross-supplemental
  fi
done
$PY report_lab.py > "$LOGS/report.log" 2>&1
$PY recommend_lab.py > "$LOGS/recommend.log" 2>&1
$PY provenance_lab.py > "$LOGS/provenance.log" 2>&1
echo "$(date -Is) FINALIZE COMPLETE" >> "$LOGS/pipeline.log"
