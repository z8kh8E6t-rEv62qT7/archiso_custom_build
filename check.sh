#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if ! command -v python >/dev/null 2>&1; then
    printf '错误：检查配置需要 Python 3（Arch 软件包 python）。\n' >&2
    exit 1
fi
exec python "$project_dir/scripts/check.py" "$@"
