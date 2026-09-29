#!/usr/bin/env bash
set -euo pipefail
umask 022
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

case "${1:-}" in
    --check)
        [[ $# == 1 ]] || { printf '用法：%s [--check|--help]\n' "$0" >&2; exit 2; }
        exec "$project_dir/check.sh" --host
        ;;
    --help|-h)
        printf '用法：%s [--check|--help]\n无参数：检查后构建 ISO（需要 root）。\n--check：仅检查配置和宿主依赖，不下载、不构建。\n' "$0"
        exit 0
        ;;
    '') [[ $# == 0 ]] || exit 2 ;;
    *) printf '未知参数：%s\n' "$1" >&2; exit 2 ;;
esac

"$project_dir/check.sh" --host
if (( EUID != 0 )); then
    printf '错误：构建需要 root，请运行 sudo %q；检查本身不需要 root。\n' "$0" >&2
    exit 1
fi
# Never reuse a previous mkarchiso work directory or remove a failed build.
# Reject symlinks so generated data stays on the intended project filesystem.
for directory in work out; do
    if [[ -L "$project_dir/$directory" ]]; then
        printf '错误：%s 不能是符号链接。\n' "$project_dir/$directory" >&2
        exit 1
    fi
done
mkdir -p -- "$project_dir/work" "$project_dir/out"
work_dir=$(mktemp -d "$project_dir/work/build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
out_dir="$project_dir/out/${work_dir##*/}"
mkdir -- "$out_dir"
printf '工作目录：%s\n输出目录：%s\n' "$work_dir" "$out_dir"
mkarchiso -v -m iso -w "$work_dir" -o "$out_dir" "$project_dir/configs/releng" 2>&1 | tee "$out_dir/build.log"
printf '构建完成：%s\n' "$out_dir"
