#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$task_root/toolchains/linux/extracted/usr/bin:$task_root/toolchains/linux/uv-aarch64-unknown-linux-gnu:$task_root/toolchains/linux/qmk-venv/bin:$PATH"
# The Python entry owns paths, QMK invocation and manifest import. This file
# only makes the optional workspace toolchain available in WSL/Linux.
cd "$task_root"
exec uv run "$task_root/tools/build_bat68.py" "$@"
