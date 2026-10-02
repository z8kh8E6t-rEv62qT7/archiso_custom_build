#!/usr/bin/env bash
set -euo pipefail
umask 022
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
asset_dir="$project_dir/configs/releng/airootfs/usr/local/lib/krdp-pointer-fix"
source_commit=270dcf01851229134f74fa7d90ac338ec788ec67

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf '用法：%s\n从固定 KRDP 6.7.5 源码重建镜像内的临时鼠标修复库。\n需要 git、cmake、ninja、C++ 编译器、extra-cmake-modules、plasma-wayland-protocols 和 KRDP 构建依赖；不会自动安装依赖。\n' "$0"
    exit 0
fi
[[ $# == 0 ]] || exit 2
if (( EUID == 0 )); then
    printf '请以普通用户运行此脚本。\n' >&2
    exit 1
fi
"$project_dir/configs/releng/airootfs/usr/local/bin/check-krdp-pointer-fix"
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/archiso-krdp-pointer-fix-XXXXXX")
printf '构建目录：%s\n' "$build_dir"
git clone --depth 1 --branch v6.7.5 https://invent.kde.org/plasma/krdp.git "$build_dir/source"
[[ $(git -C "$build_dir/source" rev-parse HEAD) == "$source_commit" ]] || {
    printf 'KRDP 源码提交与固定记录不符。\n' >&2
    exit 1
}
git -C "$build_dir/source" apply --check "$asset_dir/virtual-pointer.patch"
git -C "$build_dir/source" apply "$asset_dir/virtual-pointer.patch"
cmake -S "$build_dir/source" -B "$build_dir/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF
cmake --build "$build_dir/build" --target KRdp --parallel 8
install -m 644 "$build_dir/build/bin/libKRdp.so.6.7.5" "$asset_dir/libKRdp.so.6"
strip --strip-unneeded "$asset_dir/libKRdp.so.6"
install -d "$asset_dir/LICENSES"
install -m 644 "$build_dir/source/LICENSES/"*.txt "$asset_dir/LICENSES/"
(
    cd -- "$asset_dir"
    sha256sum libKRdp.so.6 virtual-pointer.patch > SHA256SUMS
)
printf '修复库已写入镜像覆盖目录。运行 ./check.sh 检查后再构建 ISO。\n'
