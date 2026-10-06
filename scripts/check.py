#!/usr/bin/env python3
"""Offline consistency checks for this editable Archiso profile; no downloads."""
import argparse
from collections import Counter
import hashlib
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


def check_grub_menu(path):
    config = read(path)
    label = path.relative_to(PROFILE)
    require(re.search(r"^default=archlinux-rt$", config, re.M) and
            re.search(r"^timeout=15$", config, re.M), f"{label} 应默认 linux-rt 普通启动并等待 15 秒")
    # These templates use top-level menuentry blocks; check each kernel/mode pair.
    entries = re.findall(r"^menuentry [^\n]* --id '([^']+)' \{\n(.*?)^\}", config, re.M | re.S)
    for kernel, entry_id in (("linux-rt", "archlinux-rt"), ("linux", "archlinux"), ("linux-lts", "archlinux-lts")):
        for suffix, copy in (("", "n"), ("-copytoram", "y"), ("-accessibility", "n")):
            bodies = [body for name, body in entries if name == entry_id + suffix]
            require(len(bodies) == 1, f"{label} 应唯一包含启动项 {entry_id + suffix}")
            if len(bodies) != 1:
                continue
            body = bodies[0]
            linux = re.findall(r"^\s*linux\s+(.*)$", body, re.M)
            initrd = re.findall(r"^\s*initrd\s+(.*)$", body, re.M)
            base = "/%INSTALL_DIR%/boot/%ARCH%/"
            require(len(linux) == 1 and linux[0].split()[:1] == [base + "vmlinuz-" + kernel] and
                    initrd == [base + "initramfs-" + kernel + ".img"],
                    f"{label}:{entry_id + suffix} 必须使用 ISO 中配套的内核和 initramfs")
            args = linux[0].split()[1:] if len(linux) == 1 else []
            required_args = {f"copytoram={copy}", "cow_spacesize=4G", "%KERNEL_PARAMS%",
                             "archisobasedir=%INSTALL_DIR%"}
            if path.name == "loopback.cfg":
                required_args |= {'img_dev=UUID=${archiso_img_dev_uuid}', 'img_loop="${iso_path}"'}
            else:
                required_args.add("archisosearchuuid=%ARCHISO_UUID%")
            require(required_args <= set(args) and
                    [arg for arg in args if arg.startswith("copytoram=")] == [f"copytoram={copy}"] and
                    ("accessibility=on" in args) == (suffix == "-accessibility"),
                    f"{label}:{entry_id + suffix} 启动参数不完整或模式不匹配")


def check_syslinux_menu():
    config = read(PROFILE / "syslinux/archiso_sys.cfg")
    require(re.search(r"^DEFAULT archrt$", config, re.M) and
            re.search(r"^TIMEOUT 150$", config, re.M), "BIOS 应默认 linux-rt 普通启动并等待 15 秒")
    entries = re.split(r"^LABEL ", read(PROFILE / "syslinux/archiso_sys-linux.cfg"), flags=re.M)[1:]
    for kernel, entry_id in (("linux-rt", "archrt"), ("linux", "arch"), ("linux-lts", "archlts")):
        for suffix, copy in (("", "n"), ("ram", "y"), ("speech", "n")):
            bodies = [entry for entry in entries if entry.splitlines()[0] == entry_id + suffix]
            require(len(bodies) == 1, f"BIOS 应唯一包含启动项 {entry_id + suffix}")
            if len(bodies) != 1:
                continue
            body = bodies[0]
            base = "/%INSTALL_DIR%/boot/%ARCH%/"
            require(re.findall(r"^LINUX (.+)$", body, re.M) == [base + "vmlinuz-" + kernel] and
                    re.findall(r"^INITRD (.+)$", body, re.M) == [base + "initramfs-" + kernel + ".img"],
                    f"BIOS:{entry_id + suffix} 必须使用配套的内核和 initramfs")
            append = re.findall(r"^APPEND (.+)$", body, re.M)
            args = append[0].split() if len(append) == 1 else []
            require({"archisobasedir=%INSTALL_DIR%", "archisosearchuuid=%ARCHISO_UUID%",
                     "cow_spacesize=4G", "%KERNEL_PARAMS%"} <= set(args) and
                    [arg for arg in args if arg.startswith("copytoram=")] == [f"copytoram={copy}"] and
                    ("accessibility=on" in args) == (suffix == "speech"),
                    f"BIOS:{entry_id + suffix} 启动参数不完整或模式不匹配")


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
    require({"bluez", "bluez-utils", "pipewire-audio", "pipewire-pulse", "wireplumber"} <= pkgs,
            "蓝牙音频采集需要 BlueZ、PipeWire 音频组件和 WirePlumber")
    require(target(SYSTEM / "bluetooth.target.wants/bluetooth.service") ==
            "/usr/lib/systemd/system/bluetooth.service", "蓝牙服务未启用")
    bluetooth = read(AIROOT / "etc/bluetooth/main.conf")
    require(all(re.search(pattern, bluetooth, re.M) for pattern in (
        r"^Name\s*=\s*archlive\s*$", r"^Class\s*=\s*0x000414\s*$",
        r"^AutoEnable\s*=\s*true\s*$")), "蓝牙必须自动启用并以 archlive 音响类别提供服务")
    daemon = read(SYSTEM / "bluetooth.service.d/audio-receiver.conf")
    require("ExecStart=\n" in daemon and
            "ExecStart=/usr/lib/bluetooth/bluetoothd --noplugin=hostname" in daemon,
            "应禁用 BlueZ hostname 插件，防止覆盖音响类别")
    inputs = read(AIROOT / "etc/wireplumber/wireplumber.conf.d/51-bluetooth-input.conf")
    require('node.name = "~bluez_input.*"' in inputs and
            'bluez5.media-source-role = "input"' in inputs,
            "所有手机的蓝牙音频应作为应用输入")
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
    required = {"base", "linux", "linux-lts", "linux-rt", "linux-firmware", "mkinitcpio", "mkinitcpio-archiso", "syslinux", "grub"}
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
        require(set(modes.split()) == {"bios.syslinux", "uefi.grub"}, "应使用 BIOS Syslinux 和 UEFI GRUB，共用 ISO 中的启动文件")
        require(builds == "iso", "本工程仅构建 ISO")
        require(user_mode == "0:0:755", "setup-live-user 的 file_permissions 应为 0:0:755")
        require(sudo_mode == "0:0:440", "sudoers 的 file_permissions 应为 0:0:440")
    for path in ("syslinux/syslinux.cfg", "syslinux/archiso_sys-linux.cfg",
                 "grub/grub.cfg", "grub/loopback.cfg"):
        require((PROFILE / path).is_file(), f"缺少启动配置：{path}")
    for path in (PROFILE / "grub/grub.cfg", PROFILE / "grub/loopback.cfg"):
        check_grub_menu(path)
    check_syslinux_menu()
    init = read(AIROOT / "etc/mkinitcpio.conf.d/archiso.conf")
    result = subprocess.run(["bash", "-c", 'source "$1"; '
                             '[[ $MODULES_DECOMPRESS == yes && $COMPRESSION == xz '
                             '&& ${COMPRESSION_OPTIONS[*]} == -9e ]]',
                             "bash", str(AIROOT / "etc/mkinitcpio.conf.d/archiso.conf")],
                            capture_output=True, text=True)
    require(result.returncode == 0, "initramfs 应启用 MODULES_DECOMPRESS=yes，并使用 XZ -9e 统一压缩驱动和固件")
    require(bool(re.search(r"\barchiso\b", init)) and "filesystems" in init, "initramfs 必须保留 archiso 和 filesystems hooks")
    require(bool(re.search(r"^MODULES=.*\berofs\b", init, re.M)), "EROFS 镜像需要在 initramfs MODULES 中保留 erofs")
    require(all(re.search(rf"^MODULES=.*\b{module}\b", init, re.M)
                for module in ("thunderbolt", "thunderbolt_net")),
            "雷电支持需要在 initramfs MODULES 中保留 thunderbolt 和 thunderbolt_net")
    require("bolt" in pkgs, "雷电设备授权需要 bolt")
    nvidia = {"nvidia-open-dkms", "nvidia-utils"}
    has_modules = bool(re.search(r"^MODULES=.*\bnvidia\b", init, re.M))
    has_nvidia_params = "nvidia_drm.modeset=1" in read(PROFILE / "profiledef.sh")
    require(not (pkgs & nvidia) or nvidia <= pkgs, "三内核 NVIDIA 配置需要同时包含 nvidia-open-dkms 和 nvidia-utils")
    require(not (pkgs & {"nvidia-open", "nvidia-open-lts"}), "NVIDIA 预编译包与 DKMS 驱动冲突，应使用 nvidia-open-dkms")
    require(has_modules == (nvidia <= pkgs), "NVIDIA 包与 MODULES 不一致：删除驱动时同步移除 NVIDIA MODULES 和启动参数")
    require(has_nvidia_params == (nvidia <= pkgs), "NVIDIA 启动参数与包清单不一致")
    if nvidia <= pkgs:
        require({"base-devel", "linux-headers", "linux-lts-headers", "linux-rt-headers"} <= pkgs,
                "NVIDIA DKMS 需要编译工具和三个内核各自的 headers")
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
        require(target(SYSTEM / "getty@tty1.service") == "/dev/null", "tty1 应保留给 SDDM，屏蔽其 getty")
        require(target(SYSTEM / "getty.target.wants/getty@tty2.service") == "/usr/lib/systemd/system/getty@.service",
                "应启用 tty2 救援终端")
        console = read(SYSTEM / "getty@tty2.service.d/autologin.conf")
        require("ExecStart=\n" in console and "--autologin root" in console,
                "tty2 应保留 root 自动登录")
        require(not (SYSTEM / "getty@tty1.service.d/autologin.conf").exists(),
                "root 自动登录应从 tty1 移至 tty2")
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
    require('Option "XkbLayout" "us"' in read(AIROOT / "etc/X11/xorg.conf.d/00-keyboard.conf"),
            "X11／SDDM 键盘布局应为 us")
    require("LayoutList=us" in read(skel / ".config/kxkbrc"), "Plasma 键盘布局应为 us")
    # Include PXE and GRUB templates, not just the default local boot entry.
    boot_files = [*PROFILE.glob("syslinux/*.cfg"), *PROFILE.glob("grub/*.cfg")]
    for boot_file in boot_files:
        for number, line in enumerate(read(boot_file).splitlines(), 1):
            if re.match(r"\s*(?:APPEND|linux|options)\s", line) and "archisobasedir=" in line:
                require(line.split().count("cow_spacesize=4G") == 1,
                        f"{boot_file.relative_to(PROFILE)}:{number} 应设置 cow_spacesize=4G")
    print(f"包清单：{len(packages)} 项；静态检查不验证仓库可用性或解析依赖。")


def check_host():
    require(os.uname().machine == "x86_64", "请在 x86_64 Arch Linux 宿主上构建")
    commands = ("mkarchiso", "pacman", "pacman-conf", "pacstrap", "mkinitcpio", "mkfs.erofs", "xorriso",
                "mkfs.fat", "mcopy", "mmd", "bsdtar", "unshare", "mount", "script", "mktemp",
                "grub-mkstandalone", "grub-script-check")
    missing = [name for name in commands if shutil.which(name) is None]
    require(not missing, f"缺少构建工具：{', '.join(missing)}。参见 README.md 的宿主准备命令")
    for asset in ("/usr/lib/grub/x86_64-efi/moddep.lst", "/usr/lib/grub/x86_64-efi/linux.mod",
                  "/usr/lib/grub/x86_64-efi/iso9660.mod", "/usr/lib/grub/x86_64-efi/search_fs_file.mod",
                  "/usr/share/grub/sbat.csv"):
        require(Path(asset).is_file(), f"缺少 UEFI GRUB 构建文件：{asset}；请安装宿主 grub 包")
    if shutil.which("grub-script-check"):
        for path in (PROFILE / "grub/grub.cfg", PROFILE / "grub/loopback.cfg"):
            result = subprocess.run(["grub-script-check", str(path)], capture_output=True, text=True)
            require(result.returncode == 0, f"GRUB 语法错误：{path.name}：{result.stderr.strip()}")
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


def check_pointer_fix():
    assets = AIROOT / "usr/local/lib/krdp-pointer-fix"
    checksums = read(assets / "SHA256SUMS").splitlines()
    require(len(checksums) == 2, "KRDP 临时修复需要库和补丁的 SHA-256 记录")
    expected_files = {"libKRdp.so.6", "virtual-pointer.patch"}
    seen = set()
    for line in checksums:
        fields = line.split()
        if len(fields) != 2 or fields[1] not in expected_files or fields[1] in seen:
            require(False, "KRDP 临时修复的校验记录无效")
            continue
        checksum, name = fields
        seen.add(name)
        path = assets / name
        require(path.is_file() and not path.is_symlink(), f"缺少 KRDP 临时修复文件：{name}")
        if path.is_file():
            require(hashlib.sha256(path.read_bytes()).hexdigest() == checksum,
                    f"KRDP 临时修复校验失败：{name}；请运行 scripts/build-krdp-pointer-fix.sh 重建")
    require(seen == expected_files, "KRDP 临时修复的校验记录不完整")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="store_true", help="同时检查构建宿主依赖，不要求 root")
    parser.add_argument("--aur", action="store_true", help="检查预先构建的本地 AUR 包及仓库")
    args = parser.parse_args()
    check_profile()
    check_pointer_fix()
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
