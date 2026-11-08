#!/usr/bin/env bash
# Freeze the current commit into its own folder for a long run, so later pulls never change a running job.
# Usage: scripts/snapshot.sh [gpu]   -> prints the snapshot path (~/projects/trustqem-runs/<short sha>[-gpu])
set -euo pipefail
cd "$(dirname "$0")/.."
sha=$(git rev-parse --short HEAD)
target="$HOME/projects/trustqem-runs/${sha}${1:+-$1}"
if [ ! -d "$target" ]; then
  git worktree add --detach "$target" HEAD >/dev/null
  (cd "$target" && uv sync -q)
  if [ "${1:-}" = "gpu" ]; then
    (cd "$target" && VIRTUAL_ENV=.venv uv pip uninstall -q qiskit-aer && VIRTUAL_ENV=.venv uv pip install -q "qiskit-aer-gpu==0.18.*")
  fi
fi
echo "$target"
