#!/usr/bin/env python3
"""Offline consistency checks for this editable Archiso profile; no downloads."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "configs" / "releng"
AIROOT = PROFILE / "airootfs"
SYSTEM = AIROOT / "etc/systemd/system"
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def read(path):
    try:
        return path.read_text()
    except (OSError, UnicodeError) as exc:
        errors.append(f"无法读取 {path.relative_to(ROOT)}：{exc}")
        return ""


def target(path):
    return os.readlink(path) if path.is_symlink() else None


def profile_values():
    # profiledef.sh is executable configuration, as it is for mkarchiso itself.
    # Run in a separate bash process with the same associative-array declaration.
    shell = r'''
set -eu
declare -A file_permissions=()
source "$1"
printf '%s\0' "$arch" "$iso_name" "$iso_label" "$install_dir" "$pacman_conf" \
    "$airootfs_image_type" "${bootmodes[*]}" "${buildmodes[*]}" \
    "${file_permissions[/usr/local/bin/setup-live-user]:-}" \
    "${file_permissions[/etc/sudoers.d/10-liveuser]:-}"
'''
    result = subprocess.run(["bash", "-c", shell, "bash", str(PROFILE / "profiledef.sh")],
                            capture_output=True, text=True)
    require(result.returncode == 0, f"profiledef.sh 无法加载：{result.stderr.strip()}")
    return result.stdout.split("\0")[:-1] if result.returncode == 0 else []


def check_profile():
    for script in (ROOT / "check.sh", ROOT / "build.sh", ROOT / "build-aur.sh", PROFILE / "profiledef.sh",
                   AIROOT / "usr/local/bin/setup-live-user",
                   AIROOT / "usr/local/bin/setup-live-timezone",
                   AIROOT / "etc/NetworkManager/dispatcher.d/90-live-timezone"):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        require(result.returncode == 0, f"Shell 语法错误：{script.name}：{result.stderr.strip()}")
        require(os.access(script, os.X_OK), f"缺少可执行权限：{script.relative_to(ROOT)}")
    packages = []
    for number, line in enumerate(read(PROFILE / "packages.x86_64").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        require(bool(re.fullmatch(r"[a-z0-9@_+][a-z0-9@_.+\-]*", line)),
                f"packages.x86_64:{number} 应为单独的包名，不支持行尾注释或多余空格")
        packages.append(line)
    duplicate = sorted(p for p, count in Counter(packages).items() if count > 1)
    require(not duplicate, f"包清单有重复项：{', '.join(duplicate)}")
    pkgs = set(packages)
    require({"curl", "libgcc", "libstdc++", "tzdata"} <= pkgs,
            "ipiptimezone 需要 curl、libgcc、libstdc++ 和 tzdata")
    for name in ("ipiptimezone", "v4.ipdb", "v6.ipdb"):
        asset = AIROOT / "usr/local/lib/ipiptimezone" / name
        require(asset.is_file() and not asset.is_symlink() and asset.stat().st_size > 0,
                f"缺少内置时区资产（应为实际文件）：{name}")
    require(target(AIROOT / "usr/local/bin/ipiptimezone") == "../lib/ipiptimezone/ipiptimezone",
            "ipiptimezone 命令链接缺失")
    require(target(SYSTEM / "timers.target.wants/live-timezone.timer") == "../live-timezone.timer",
            "时区重试定时器未启用")
    for executable in ("/usr/local/lib/ipiptimezone/ipiptimezone", "/usr/local/bin/setup-live-timezone",
                       "/etc/NetworkManager/dispatcher.d/90-live-timezone"):
        result = subprocess.run(["bash", "-c", 'declare -A file_permissions=(); source "$1"; '
                                 '[[ ${file_permissions[$2]:-} == 0:0:755 ]]',
                                 "bash", str(PROFILE / "profiledef.sh"), executable])
        require(result.returncode == 0, f"镜像内可执行文件权限应为 0:0:755：{executable}")
    if "grml-zsh-config" in pkgs:
        zshrc = AIROOT / "etc/skel/.zshrc"
        require(not zshrc.exists() and not zshrc.is_symlink(),
                "etc/skel/.zshrc 由 grml-zsh-config 提供，预放入会导致文件冲突；请用 etc/skel/.zshrc.local 定制")
    required = {"base", "linux", "linux-lts", "linux-firmware", "mkinitcpio", "mkinitcpio-archiso", "syslinux"}
    require(required <= pkgs, f"缺少本工程启动必需包：{', '.join(sorted(required - pkgs))}")
    values = profile_values()
    require(len(values) == 10, "profiledef.sh 未返回完整配置")
    if len(values) == 10:
        arch, name, label, install, pacman, fs, modes, builds, user_mode, sudo_mode = values
        require(arch == "x86_64", "本工程仅支持 x86_64")
        require(bool(re.fullmatch(r"[A-Za-z0-9._-]+", name)), "iso_name 应为安全文件名")
        require(bool(re.fullmatch(r"[A-Z0-9_]{1,32}", label)), "iso_label 应为最多 32 位大写字母、数字或下划线")
        require(bool(re.fullmatch(r"[a-z0-9]{1,30}", install)), "install_dir 格式不合法")
        require(pacman == "pacman.conf" and (PROFILE / pacman).is_file(), "本工程需要 configs/releng/pacman.conf")
        require(fs == "erofs", "本工程构建依赖检查针对 EROFS")
        require(set(modes.split()) == {"bios.syslinux", "uefi.systemd-boot"}, "应保留 BIOS 和 UEFI 启动模式")
        require(builds == "iso", "本工程仅构建 ISO")
        require(user_mode == "0:0:755", "setup-live-user 的 file_permissions 应为 0:0:755")
        require(sudo_mode == "0:0:440", "sudoers 的 file_permissions 应为 0:0:440")
    for path in ("syslinux/syslinux.cfg", "syslinux/archiso_sys-linux.cfg",
                 "efiboot/loader/loader.conf", "efiboot/loader/entries/01-archiso-linux.conf",
                 "efiboot/loader/entries/02-archiso-copytoram-linux.conf",
                 "efiboot/loader/entries/04-archiso-linux-lts.conf",
                 "efiboot/loader/entries/05-archiso-copytoram-linux-lts.conf",
                 "efiboot/loader/entries/06-archiso-speech-linux-lts.conf"):
        require((PROFILE / path).is_file(), f"缺少启动配置：{path}")
    init = read(AIROOT / "etc/mkinitcpio.conf.d/archiso.conf")
    require(bool(re.search(r"\barchiso\b", init)) and "filesystems" in init, "initramfs 必须保留 archiso 和 filesystems hooks")
    require(bool(re.search(r"^MODULES=.*\berofs\b", init, re.M)), "EROFS 镜像需要在 initramfs MODULES 中保留 erofs")
    require(all(re.search(rf"^MODULES=.*\b{module}\b", init, re.M)
                for module in ("thunderbolt", "thunderbolt_net")),
            "雷电支持需要在 initramfs MODULES 中保留 thunderbolt 和 thunderbolt_net")
    require("bolt" in pkgs, "雷电设备授权需要 bolt")
    nvidia = {"nvidia-open", "nvidia-open-lts", "nvidia-utils"}
    has_modules = bool(re.search(r"^MODULES=.*\bnvidia\b", init, re.M))
    has_nvidia_params = "nvidia_drm.modeset=1" in read(PROFILE / "profiledef.sh")
    require(not (pkgs & nvidia) or nvidia <= pkgs, "双内核 NVIDIA 配置需要同时包含 nvidia-open、nvidia-open-lts 和 nvidia-utils")
    require(has_modules == (nvidia <= pkgs), "NVIDIA 包与 MODULES 不一致：删除驱动时同步移除 NVIDIA MODULES 和启动参数")
    require(has_nvidia_params == (nvidia <= pkgs), "NVIDIA 启动参数与包清单不一致")
    if nvidia <= pkgs:
        require(all(module in init for module in ("nvidia_modeset", "nvidia_uvm", "nvidia_drm")), "NVIDIA initramfs 模块不完整")
    desktop = {"plasma-meta", "sddm"}
    if pkgs & desktop or (SYSTEM / "display-manager.service").is_symlink():
        require(desktop <= pkgs, "桌面配置需要 plasma-meta 和 sddm；移除桌面时同步调整相关服务与默认 target")
        require(target(SYSTEM / "display-manager.service") == "/usr/lib/systemd/system/sddm.service", "SDDM 未启用")
        require(target(SYSTEM / "default.target") == "/usr/lib/systemd/system/graphical.target", "默认 target 应为 graphical.target")
        autologin = read(AIROOT / "etc/sddm.conf.d/autologin.conf")
        require("User=liveuser" in autologin and "Session=plasma.desktop" in autologin, "SDDM 自动登录配置不完整")
        ordering = read(SYSTEM / "sddm.service.d/live-user.conf")
        require("Requires=setup-live-user.service" in ordering and "After=setup-live-user.service" in ordering,
                "SDDM 必须依赖并等待用户初始化服务")
    require({"sudo", "zsh"} <= pkgs, "liveuser 初始化需要 sudo 和 zsh")
    setup = read(SYSTEM / "setup-live-user.service")
    require("Before=sddm.service" in setup and "ExecStart=/usr/local/bin/setup-live-user" in setup,
            "用户初始化服务缺少启动命令或排序")
    require("liveuser ALL=(ALL:ALL) NOPASSWD: ALL" in read(AIROOT / "etc/sudoers.d/10-liveuser"), "liveuser 免密 sudo 配置缺失")
    require({"networkmanager", "wpa_supplicant"} <= pkgs, "当前网络配置需要 networkmanager 和 wpa_supplicant")
    require(target(SYSTEM / "multi-user.target.wants/NetworkManager.service") == "/usr/lib/systemd/system/NetworkManager.service", "NetworkManager 未启用")
    for service in ("systemd-networkd.service", "systemd-networkd.socket", "systemd-networkd-wait-online.service"):
        require(target(SYSTEM / service) == "/dev/null", f"应屏蔽冲突服务：{service}")
    for link in SYSTEM.rglob("*"):
        destination = target(link)
        if destination is None or destination == "/dev/null":
            continue
        require(not any(word in destination for word in ("systemd-networkd", "iwd.service")),
                f"残留竞争网络服务：{link.relative_to(SYSTEM)}")
        # Absolute /usr targets belong to packages in the future image, not the host.
        if destination.startswith("/etc/"):
            require((AIROOT / destination.lstrip("/")).exists(), f"失效 overlay 链接：{link.relative_to(PROFILE)}")
        elif not destination.startswith("/"):
            require((link.parent / destination).exists(), f"失效相对链接：{link.relative_to(PROFILE)}")
    repositories = set(re.findall(r"^\[([^\]]+)\]", read(PROFILE / "pacman.conf"), re.M)) - {"options"}
    require(repositories == {"core", "extra"}, "默认仓库应仅包含 core 和 extra；增加仓库时请同步调整检查规则")
    require(read(AIROOT / "etc/locale.conf").strip() == "LANG=zh_CN.UTF-8", "默认语言应为 zh_CN.UTF-8，不全局设置 LC_ALL")
    locales = set(read(AIROOT / "etc/locale.gen").splitlines())
    require({"zh_CN.UTF-8 UTF-8", "en_US.UTF-8 UTF-8"} <= locales, "必须生成中英文 UTF-8 locale")
    chinese_packages = {"fcitx5", "fcitx5-rime", "fcitx5-gtk", "fcitx5-qt", "fcitx5-configtool",
                        "noto-fonts-cjk", "firefox-i18n-zh-cn", "rime-ice-pinyin-git"}
    require(chinese_packages <= pkgs, f"缺少中文环境软件包：{', '.join(sorted(chinese_packages - pkgs))}")
    skel = AIROOT / "etc/skel"
    require("InputMethod=/usr/share/applications/org.fcitx.Fcitx5.desktop" in read(skel / ".config/kwinrc"),
            "KWin 必须启动 Fcitx5")
    require("Hidden=true" in read(skel / ".config/autostart/org.fcitx.Fcitx5.desktop"), "必须避免重复自启动 Fcitx5")
    require("DefaultIM=rime" in read(skel / ".config/fcitx5/profile"), "默认输入法应为 Rime")
    require("0=Control+space" in read(skel / ".config/fcitx5/config"), "输入法切换应为 Ctrl+Space")
    require("__include: rime_ice_suggestion:/" in read(skel / ".local/share/fcitx5/rime/default.custom.yaml"),
            "Rime 必须加载雾凇推荐配置")
    require("KEYMAP=us" in read(AIROOT / "etc/vconsole.conf"), "键盘配置应为 us")
    print(f"包清单：{len(packages)} 项；静态检查不验证仓库可用性或解析依赖。")


def check_host():
    require(os.uname().machine == "x86_64", "请在 x86_64 Arch Linux 宿主上构建")
    commands = ("mkarchiso", "pacman", "pacman-conf", "pacstrap", "mkinitcpio", "mkfs.erofs", "xorriso",
                "mkfs.fat", "mcopy", "mmd", "bsdtar", "unshare", "mount", "script", "mktemp")
    missing = [name for name in commands if shutil.which(name) is None]
    require(not missing, f"缺少构建工具：{', '.join(missing)}。参见 README.md 的宿主准备命令")
    if shutil.which("mkfs.erofs"):
        result = subprocess.run(["mkfs.erofs", "--help"], capture_output=True, text=True)
        require(result.returncode == 0 and bool(re.search(r"\blzma\b", result.stdout + result.stderr)),
                "mkfs.erofs 必须支持 LZMA 压缩；请安装启用 LZMA 的 erofs-utils")
    if shutil.which("pacman"):
        result = subprocess.run(["pacman", "-Q", "archiso"], capture_output=True, text=True)
        require(result.returncode == 0, "未安装 Archiso；模板来源为 v91")
        if result.returncode == 0:
            version = result.stdout.strip().split()[-1]
            major = version.split(":")[-1].split(".")[0].split("-")[0]
            expected = str(json.loads(read(ROOT / "reference/source.json"))["archiso_major"])
            require(major == expected, f"Archiso 版本 {version} 与模板 v{expected} 不匹配，请先审核模板兼容性")
    mirrors = Path("/etc/pacman.d/mirrorlist")
    require(mirrors.is_file() and bool(re.search(r"^\s*Server\s*=", mirrors.read_text() if mirrors.is_file() else "", re.M)),
            "宿主 mirrorlist 没有启用的 Server；请先配置镜像源")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="store_true", help="同时检查构建宿主依赖，不要求 root")
    parser.add_argument("--aur", action="store_true", help="检查预先构建的本地 AUR 包及仓库")
    args = parser.parse_args()
    check_profile()
    if args.host:
        check_host()
    if args.aur:
        result = subprocess.run([sys.executable, str(ROOT / "scripts/aur_repo.py"), "check"])
        require(result.returncode == 0, "本地 AUR 仓库检查失败；请先以普通用户运行 ./build-aur.sh")
    if errors:
        for message in errors:
            print(f"错误：{message}", file=sys.stderr)
        return 1
    print("检查通过。本次仅检查配置，不代表 ISO 构建或启动验证。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
