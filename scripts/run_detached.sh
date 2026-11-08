#!/usr/bin/env bash
# Start a long run in its own tmux session so it survives a closed laptop or a dropped VPN.
# Usage: scripts/run_detached.sh <name> <command...>
# The command and the env it needs are written to logs/<name>.run.sh, so quoting inside the command is safe.
# Env passed through: TRUSTQEM_WORKERS, TRUSTQEM_GPUS, TRUSTQEM_AER_DEVICE, TRUSTQEM_AER_PRECISION, TRUSTQEM_CACHE,
# CUDA_VISIBLE_DEVICES. Ends with logs/<name>.DONE (exit 0) or logs/<name>.FAILED (with the exit code).
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
runner="logs/${name}.run.sh"
{
  echo "#!/usr/bin/env bash"
  echo "cd $(printf '%q' "$PWD")"
  # tmux hands every session the env of whoever started the tmux server, so clear our settings first
  echo "unset TRUSTQEM_WORKERS TRUSTQEM_GPUS TRUSTQEM_AER_DEVICE TRUSTQEM_AER_PRECISION TRUSTQEM_CACHE CUDA_VISIBLE_DEVICES"
  echo "export OMP_NUM_THREADS=1"
  for variable in TRUSTQEM_WORKERS TRUSTQEM_GPUS TRUSTQEM_AER_DEVICE TRUSTQEM_AER_PRECISION TRUSTQEM_CACHE \
                  CUDA_VISIBLE_DEVICES; do
    if [ -n "${!variable:-}" ]; then echo "export $variable=$(printf '%q' "${!variable}")"; fi
  done
  printf 'echo "started $(date -Is) on $(hostname): %s" > logs/%s.log\n' "$(printf '%q ' "$@" | sed 's/"/\\"/g')" "$name"
  printf 'nice -n 10 %s >> logs/%s.log 2>&1\n' "$(printf '%q ' "$@")" "$name"
  echo 'code=$?'
  printf 'if [ $code -eq 0 ]; then date -Is > logs/%s.DONE; else echo "exit $code $(date -Is)" > logs/%s.FAILED; fi\n' \
    "$name" "$name"
} > "$runner"
tmux new-session -d -s "$session" "bash $runner"
echo "started $session; log: logs/${name}.log"
