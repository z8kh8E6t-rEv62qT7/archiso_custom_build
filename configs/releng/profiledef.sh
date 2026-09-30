#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="archlinux-custom"
iso_label="ARCHCUSTOM_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="Custom Arch Linux Live"
iso_application="Custom Arch Linux KDE Live/Rescue"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
arch="x86_64"
buildmodes=('iso')
install_dir="arch"
kernel_params_x86_64="nvidia_drm.modeset=1"
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="erofs"
# Extreme LZMA, 1 MiB physical clusters and packed tails with parallel fragment deduplication.
# Do not add global dedupe: erofs-utils 1.9.4 would fall back to serial compression.
airootfs_image_tool_options=(
  '-zlzma,109'
  '-C1048576'
  '-Efragments,ztailpacking,fragdedupe=inode'
  '--workers=16'
)
file_permissions=(
  ["/usr/local/bin/setup-live-user"]="0:0:755"
  ["/etc/sudoers.d/10-liveuser"]="0:0:440"
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
)
