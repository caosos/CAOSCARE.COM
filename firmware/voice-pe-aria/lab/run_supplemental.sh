#!/usr/bin/env bash
# Mandatory supplemental candidates (Michael, 2026-10-04: Callista/Kestra/Krysta correction + Sivia
# addendum) - identical procedure, run after the original 15. Never alters completed results: the
# additive cross-check (extra confusion set for all models; supplemental positives for the original
# 15) is written to a separate lab_eval_supp_cross.json per model.
set -u
LAB=$(cd "$(dirname "$0")" && pwd)
PY=$HOME/caoscare-firmware-work/venv-mww/bin/python
W=$HOME/caoscare-firmware-work
LOGS=$W/lab_logs
mkdir -p "$LOGS"
cd "$LAB" || exit 1
TFL=trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite
slugs() { $PY -c "import json;print(' '.join(c['slug'] for c in json.load(open('$1'))))"; }
# 1. supplemental positives once the original positives are finished (training has started)
until ls "$LOGS"/train_*.log >/dev/null 2>&1; do sleep 60; done
$PY gen_lab.py positives supplemental > "$LOGS/gen_positives_supplemental.log" 2>&1 || exit 1
# 2. supplemental evaluation positives once the shared evaluation set is finished
until [ -f "$LOGS/gen_eval.done" ]; do sleep 60; done
$PY gen_lab.py eval supplemental > "$LOGS/gen_eval_supplemental.log" 2>&1 || exit 1
$PY gen_lab.py extra_confusion > "$LOGS/gen_extra_confusion.log" 2>&1 || exit 1
# 3. after the original pipeline: train + evaluate each supplemental model
until grep -q "PIPELINE COMPLETE" "$LOGS/pipeline.log" 2>/dev/null; do sleep 120; done
for s in $(slugs supplemental_candidates.json); do
  [ -f "$W/runs/lab/$s/$TFL" ] || $PY train_lab.py "$s" > "$LOGS/train_$s.log" 2>&1 \
    || echo "$(date -Is) TRAIN FAILED $s" >> "$LOGS/pipeline.log"
  [ -f "$W/runs/lab/$s/lab_eval.json" ] || $PY eval_lab.py "$s" > "$LOGS/eval_$s.log" 2>&1 \
    || echo "$(date -Is) EVAL FAILED $s" >> "$LOGS/pipeline.log"
  echo "$(date -Is) done supplemental $s" >> "$LOGS/pipeline.log"
done
# 4. additive cross-check for every model (original 15 + supplemental 11)
for s in $(slugs trained_candidates.json) $(slugs supplemental_candidates.json); do
  [ -f "$W/runs/lab/$s/lab_eval_supp_cross.json" ] || $PY eval_lab.py "$s" --cross-supplemental \
    > "$LOGS/cross_$s.log" 2>&1 || echo "$(date -Is) CROSS FAILED $s" >> "$LOGS/pipeline.log"
done
$PY report_lab.py > "$LOGS/report.log" 2>&1
$PY recommend_lab.py > "$LOGS/recommend.log" 2>&1
$PY provenance_lab.py > "$LOGS/provenance.log" 2>&1
echo "$(date -Is) SUPPLEMENTAL COMPLETE" >> "$LOGS/pipeline.log"
