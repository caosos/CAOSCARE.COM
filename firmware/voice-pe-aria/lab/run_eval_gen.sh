#!/usr/bin/env bash
# Generate the held-out evaluation clips, then mark completion for run_lab.sh.
set -u
LAB=$(cd "$(dirname "$0")" && pwd)
LOGS=$HOME/caoscare-firmware-work/lab_logs; mkdir -p "$LOGS"
cd "$LAB" && "$HOME/caoscare-firmware-work/venv-mww/bin/python" gen_lab.py eval > "$LOGS/gen_eval.log" 2>&1 && touch "$LOGS/gen_eval.done"
