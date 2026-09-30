#!/usr/bin/env bash
set -euo pipefail
umask 022
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

case "${1:-}" in
    --check)
        [[ $# == 1 ]] || { printf '用法：%s [--check|--help]\n' "$0" >&2; exit 2; }
        exec "$project_dir/check.sh" --host --aur
        ;;
    --help|-h)
        printf '用法：%s [--check|--help]\n无参数：检查后构建 ISO（需要 root）。\n--check：仅检查配置、宿主依赖和预先构建的 AUR 包，不下载、不构建。\n请先以普通用户运行 ./build-aur.sh 准备本地包。\n' "$0"
        exit 0
        ;;
    '') [[ $# == 0 ]] || exit 2 ;;
    *) printf '未知参数：%s\n' "$1" >&2; exit 2 ;;
esac

"$project_dir/check.sh" --host --aur
aur_repo=$(python "$project_dir/scripts/aur_repo.py" check --print-path)
if (( EUID != 0 )); then
    printf '错误：构建需要 root，请运行 sudo %q；检查本身不需要 root。\n' "$0" >&2
    exit 1
fi
# Never reuse a previous mkarchiso work directory or remove a failed build.
# Reject symlinks so generated data stays on the intended project filesystem.
for directory in work out work/cache work/cache/pacman work/cache/pacman/pkg; do
    if [[ -L "$project_dir/$directory" ]]; then
        printf '错误：%s 不能是符号链接。\n' "$project_dir/$directory" >&2
        exit 1
    fi
done
cache_dir="$project_dir/work/cache/pacman/pkg"
mkdir -p -- "$cache_dir" "$project_dir/out"
work_dir=$(mktemp -d "$project_dir/work/build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
out_dir="$project_dir/out/${work_dir##*/}"
mkdir -- "$out_dir"
# Resolve includes and replace CacheDir in a per-build config, keeping the profile portable.
pacman_conf="$work_dir/build.pacman.conf"
pacman-conf --config "$project_dir/configs/releng/pacman.conf" | while IFS= read -r line; do
    [[ "$line" =~ ^CacheDir[[:space:]]*= ]] && continue
    printf '%s\n' "$line"
    if [[ "$line" == '[options]' ]]; then
        printf 'CacheDir = %s\n' "$cache_dir"
    fi
done > "$pacman_conf"
# Trust unsigned packages only in this explicitly prepared, local build repository.
printf '\n[custom-aur]\nSigLevel = Optional TrustAll\nServer = file://%s\n' "$aur_repo" >> "$pacman_conf"
printf '工作目录：%s\n软件包缓存：%s\n输出目录：%s\n' "$work_dir" "$cache_dir" "$out_dir"
# Keep a terminal for pacman progress bars while recording output and preserving failures.
script --quiet --return --flush --echo never --log-out "$out_dir/build.log" -- \
    mkarchiso -v -m iso -C "$pacman_conf" -w "$work_dir" -o "$out_dir" "$project_dir/configs/releng"
printf '构建完成：%s\n' "$out_dir"
for iso in "$out_dir"/*.iso; do
    iso_bytes=$(stat -c %s -- "$iso")
    printf 'ISO 大小：%s 字节；当前 DVD 容量：4700372992 字节。\n' "$iso_bytes"
    if (( iso_bytes > 4700372992 )); then
        printf 'ISO 已生成，但超过当前 DVD 容量；未自动删除软件包。\n' >&2
        exit 1
    fi
done
