#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
cd "$task_root"
export UV_PROJECT_ENVIRONMENT="$task_root/.build/python/linux"
unset VIRTUAL_ENV
exec uv run --project "$task_root/util/sn34" --locked python "$task_root/util/sn34/build.py" "$@"
