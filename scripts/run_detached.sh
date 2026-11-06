#!/usr/bin/env bash
# Start a long run in its own tmux session so it survives a closed laptop or a dropped VPN.
# Usage: scripts/run_detached.sh <name> <command...>
# Env read here: TRUSTQEM_WORKERS, TRUSTQEM_GPUS, CUDA_VISIBLE_DEVICES, TRUSTQEM_AER_DEVICE, TRUSTQEM_AER_PRECISION, TRUSTQEM_CACHE
set -euo pipefail
name="$1"; shift
cd "$(dirname "$0")/.."
mkdir -p logs
session="tqem-${name}"
if tmux has-session -t "$session" 2>/dev/null; then
  echo "tmux session $session already exists; attach with: tmux attach -t $session" >&2
  exit 1
fi
rm -f "logs/${name}.DONE" "logs/${name}.FAILED"
# the command runs with low priority and one OpenMP thread per worker; its exit code decides DONE or FAILED
exports="OMP_NUM_THREADS=1 TRUSTQEM_WORKERS=${TRUSTQEM_WORKERS:-1} TRUSTQEM_AER_DEVICE=${TRUSTQEM_AER_DEVICE:-CPU}"
exports="$exports TRUSTQEM_AER_PRECISION=${TRUSTQEM_AER_PRECISION:-double}"
for optional in CUDA_VISIBLE_DEVICES TRUSTQEM_GPUS TRUSTQEM_CACHE; do
  if [ -n "${!optional:-}" ]; then exports="$exports $optional=${!optional}"; fi
done
inner="export $exports; \
echo \"started \$(date -Is) on \$(hostname): $*\" > logs/${name}.log; \
nice -n 10 $* >> logs/${name}.log 2>&1; code=\$?; \
if [ \$code -eq 0 ]; then date -Is > logs/${name}.DONE; else echo \"exit \$code \$(date -Is)\" > logs/${name}.FAILED; fi"
tmux new-session -d -s "$session" "bash -c '$inner'"
echo "started $session; log: logs/${name}.log"
