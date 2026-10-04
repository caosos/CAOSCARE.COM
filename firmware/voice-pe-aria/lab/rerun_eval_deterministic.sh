#!/usr/bin/env bash
# 2026-10-04 fairness correction: re-run ONLY evaluation + cross-check for all 26 trained models
# with the deterministic per-clip seed (eval_lab.py). No retraining. Previous outputs are kept in
# runs/lab/<slug>/superseded_2026-10-04_salted_seed/ as evidence.
set -u
LAB=$(cd "$(dirname "$0")" && pwd)
PY=$HOME/caoscare-firmware-work/venv-mww/bin/python
W=$HOME/caoscare-firmware-work
LOG=$W/lab_logs/rerun_eval_deterministic.log
cd "$LAB" || exit 1
slugs=$($PY -c "from lab_common import load_all_candidates as L; print(' '.join(c['slug'] for c in L()))")
echo "$(date -Is) START" >> "$LOG"
for s in $slugs; do
  d=$W/runs/lab/$s; old=$d/superseded_2026-10-04_salted_seed; mkdir -p "$old"
  for f in lab_eval.json lab_eval_supp_cross.json; do [ -f "$d/$f" ] && [ ! -f "$old/$f" ] && mv "$d/$f" "$old/$f"; done
  $PY eval_lab.py "$s" > "$W/lab_logs/eval2_$s.log" 2>&1 || echo "$(date -Is) EVAL FAILED $s" >> "$LOG"
  $PY eval_lab.py "$s" --cross-supplemental > "$W/lab_logs/cross2_$s.log" 2>&1 || echo "$(date -Is) CROSS FAILED $s" >> "$LOG"
  echo "$(date -Is) done $s" >> "$LOG"
done
$PY report_lab.py > "$W/lab_logs/report2.log" 2>&1 && $PY recommend_lab.py > "$W/lab_logs/recommend2.log" 2>&1 \
  && $PY provenance_lab.py > "$W/lab_logs/provenance2.log" 2>&1
echo "$(date -Is) RERUN COMPLETE" >> "$LOG"
