#!/usr/bin/env bash
set -euo pipefail
umask 022
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf '用法：%s\n以普通用户构建雾凇拼音并发布本地仓库；makepkg --syncdeps 可能通过 sudo 安装官方构建依赖。\n' "$0"
    exit 0
fi
[[ $# == 0 ]] || { printf '不支持参数，请使用 --help。\n' >&2; exit 2; }
if (( EUID == 0 )); then
    printf '请以普通用户运行 ./build-aur.sh，不要使用 sudo。\n' >&2
    exit 1
fi
for tool in git makepkg repo-add python bsdtar; do
    command -v "$tool" >/dev/null || { printf '缺少工具：%s\n' "$tool" >&2; exit 1; }
done
pacman -Q base-devel >/dev/null 2>&1 || {
    printf '请先安装构建工具：sudo pacman -S --needed base-devel git\n' >&2
    exit 1
}
[[ ! -L "$project_dir/localrepo" ]] || { printf 'localrepo 不能是符号链接。\n' >&2; exit 1; }
mkdir -p -- "$project_dir/localrepo"
run_dir=$(mktemp -d "$project_dir/localrepo/build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
exec > >(tee "$run_dir/build.log") 2>&1
printf 'AUR 构建目录：%s\n' "$run_dir"
mkdir -- "$run_dir/repo"
publish_args=()
for name in rime-ice-pinyin-git; do
    package_dir="$run_dir/$name"
    mkdir -- "$package_dir"
    git clone -- "https://aur.archlinux.org/$name.git" "$package_dir/aur"
    cd -- "$package_dir/aur"
    aur_commit=$(git rev-parse HEAD)
    # Keep artifacts local even if the caller has makepkg destination overrides.
    mkdir -- "$package_dir/packages" "$package_dir/sources" "$package_dir/logs" "$package_dir/work"
    export PKGDEST="$package_dir/packages" SRCDEST="$package_dir/sources"
    export SRCPKGDEST="$package_dir/packages" LOGDEST="$package_dir/logs" BUILDDIR="$package_dir/work"
    bash "$project_dir/scripts/aur-makepkg.sh"
    packages=()
    while IFS= read -r package; do
        # makepkg can list a hypothetical debug package even when none was produced.
        [[ ! -f "$package" || ${package##*/} == "$name-debug-"* ]] || packages+=("$package")
    done < <(makepkg --packagelist)
    [[ ${#packages[@]} == 1 ]] || { printf '预期恰好一个 %s 包。\n' "$name" >&2; exit 1; }
    upstream_commit=''
    if [[ "$name" == rime-ice-pinyin-git ]]; then
        upstream_commit=$(git -C "$package_dir/work/$name/src/rime-ice-pinyin" rev-parse HEAD)
    fi
    cp -- "${packages[0]}" "$run_dir/repo/"
    publish_args+=(--package "${packages[0]##*/}" "$aur_commit" "$upstream_commit")
done
repo-add "$run_dir/repo/custom-aur.db.tar.gz" "$run_dir/repo/"*.pkg.tar.*
python "$project_dir/scripts/aur_repo.py" publish "$run_dir/repo" "${publish_args[@]}"
printf 'AUR 仓库已准备好。下一步：sudo %s/build.sh\n' "$project_dir"
