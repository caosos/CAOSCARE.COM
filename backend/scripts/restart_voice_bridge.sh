#!/usr/bin/env bash
# Restart the Voice PE bridge backend (owner-run). Stops only the serve.py
# process listening on 192.168.122.1:8098, then starts this checkout there
# (reachable from the Home Assistant VM only). Log: /tmp/caoscare_bridge_8098.log
set -u
cd "$(dirname "$0")/.."
PID=$(ss -ltnp 2>/dev/null | awk '/192.168.122.1:8098 /{print}' | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -1)
if [ -n "$PID" ]; then kill "$PID"; sleep 2; fi
export CAOSCARE_BIND_HOST=192.168.122.1 CAOSCARE_BIND_PORT=8098 CAOSCARE_ESCALATION_AUTO=0
export CAOSCARE_RUNTIME_SHA=$(git rev-parse --short HEAD)
nohup /home/caoscare-1/CAOSCARE.COM/backend/.venv/bin/python3 serve.py > /tmp/caoscare_bridge_8098.log 2>&1 < /dev/null &
sleep 6
head -1 /tmp/caoscare_bridge_8098.log
