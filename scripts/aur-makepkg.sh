#!/usr/bin/env bash
# Run inside the AUR checkout, with the caller's makepkg destination variables.
set -euo pipefail

# GitHub occasionally sends a broken pack with protocol v2 to this live
# environment.  Protocol v1 uses the older upload-pack negotiation and avoids
# the missing-object/index-pack failure while preserving the complete mirror.
git_config=$(mktemp)
trap 'rm -f "$git_config"' EXIT
printf '[protocol]\n\tversion = 1\n' >"$git_config"
export MAKEPKG_GIT_CONFIG="$git_config"

# Retry acquisition only; never retry package build/install failures. Keep full
# VCS history because pkgver() may count commits (as rime-ice-pinyin-git does).
for attempt in 1 2 3; do
    if makepkg --verifysource; then
        exec makepkg --syncdeps --cleanbuild --log --holdver
    fi
    if (( attempt == 3 )); then
        printf '源码下载或校验连续失败 3 次；请检查上方错误及网络，构建已停止。\n' >&2
        exit 1
    fi
    printf '源码下载或校验失败，准备重试（%s/3）。\n' "$((attempt + 1))" >&2
    sleep "$((attempt * 2))"
done
