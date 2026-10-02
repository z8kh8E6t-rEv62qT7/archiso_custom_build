# 自定义 Arch Linux Live ISO

基于官方 Git 历史的可编辑 Archiso 工程，参照当前 `archlinux-kde-nvidia` Live 环境。
当前固定使用 **EROFS + LZMA extreme 109、片段去重、16 线程压缩**，initramfs 将模块和固件解压后统一以 XZ `-9e` 压缩。**当前配置已切换到 BIOS Syslinux + UEFI GRUB，共用 ISO 中的内核和 initramfs；这次引导切换尚未构建或启动验证。** 双内核和现有软件均保留。

最近一次成功构建仍使用切换前的 UEFI systemd-boot：2026-09-30 UTC 的 ISO 为 **4,578,738,176 字节（4366.625 MiB）**，比 initramfs 优化前减少 179.41 MiB（3.95%），距当前 DVD 容量尚余 116 MiB。旧产物位于 `out/build-20260930T055617Z-qMJUh1/archlinux-custom-2026.09.29-x86_64.iso`，同目录保留构建日志及 SHA-256 文件；该体积不代表 GRUB 方案，测试过程见 `reference/VALIDATION.md`。

## 工程入口

| 路径 | 用途 |
| --- | --- |
| `configs/releng/packages.x86_64` | 唯一安装包清单（含 VS Code、tk 和 Kamoso），实际项数由 `check.sh` 输出 |
| `configs/releng/profiledef.sh` | 名称、日期版本、架构、启动模式、压缩和文件权限 |
| `configs/releng/airootfs/` | 映射到新镜像根目录的文件覆盖 |
| `configs/releng/pacman.conf` | 构建镜像时使用的官方 core、extra 仓库配置 |
| `configs/releng/syslinux/` | BIOS 启动配置 |
| `configs/releng/grub/` | UEFI GRUB 主菜单及 ISO loopback 菜单 |
| `configs/releng/efiboot/` | 保留供上游同步的旧 systemd-boot 模板，当前构建不使用 |
| `check.sh`、`build-aur.sh`、`build.sh` | 配置检查、AUR 准备、ISO 构建入口 |
| `reference/` | 模板来源、官方说明和两个环境的包快照 |
| `work/`、`out/` | 实际构建时才创建；分别保存共享软件包缓存／工作数据和 ISO／日志 |

定制初始基线为官方 [Archiso v91](https://github.com/archlinux/archiso/tree/v91/configs/releng)，提交
`723da192226e1c9d5def9168f13332793c82a85e`。来源及下载归档的 SHA-256 记录在
`reference/source.json`；官方 profile 说明保存在 `reference/README.profile.upstream.rst`。
保留上游 GPL-3.0-or-later 许可，见 `LICENSE`。

## 当前行为

- x86_64、`linux` 与 `linux-lts` 双内核、BIOS Syslinux 与 UEFI GRUB 启动，根文件系统使用 EROFS + LZMA。
- 使用 Archiso 原生 `uefi.grub` 模式：EFI FAT 分区保存 GRUB 引导程序和 UEFI Shell；GRUB 定位 ISO 卷后读取 `/arch/boot/x86_64/` 中与 BIOS 共用的内核和 initramfs，不再把这四个大文件复制到 EFI 分区。按上一版产物估算有望进一步减少约 550–570 MiB，实际以重新构建结果为准。
- BIOS、UEFI 及 GRUB loopback 菜单明确提供 `Normal`（普通启动，`copytoram=n`）和 `Copy to RAM`（复制到内存，`copytoram=y`）两个入口，两套内核各自提供普通、Copy to RAM 和语音辅助启动项。默认使用 `linux` 普通启动，15 秒后自动进入；语音辅助入口也使用普通模式。普通模式需保持启动介质连接，复制到内存模式需额外内存存放压缩根文件系统。菜单修改需重新构建 ISO 才能生效。
- 所有 Live 启动入口设置 `cow_spacesize=4G`，将内存可写层上限设为 4 GiB，按实际写入占用内存；Copy to RAM 存放压缩根文件系统所用内存另计。
- 根文件系统采用 LZMA extreme 级别 109、1 MiB 物理压缩簇、文件尾部打包，以及 `fragdedupe=inode` 片段去重，使用 `--workers=16` 并行压缩。片段去重在文件数据完全相同时复用其 fragment 数据；不启用会让 erofs-utils 1.9.4 退回串行的全局 `dedupe`。
- initramfs 显式包含 `erofs` 内核模块，使用 `MODULES_DECOMPRESS="yes"` 先解压内核模块和固件，再以 XZ `-9e` 统一压缩，减少已压缩文件留在 early CPIO 中造成的体积开销；CPU 微码仍保留在 early CPIO。两套内核及硬件支持均保留，代价是启动早期解压时的内存占用增加。`squashfs-tools` 作为 Live 救援工具保留，不再用于生成根文件系统。
- KDE Plasma，SDDM 自动登录 `liveuser`，zsh，`liveuser` 免密 sudo。KDE 与 Firefox 默认简体中文，安装 Noto CJK 字体；生成 `zh_CN.UTF-8` 和 `en_US.UTF-8`，不全局设置 `LC_ALL`。
- KDE 远程桌面认证兼容修复：`/etc/FreeRDP/FreeRDP/HKLM.reg` 将 FreeRDP 服务端的 `ExtSecurity` 设为 `0`，避免 KRDP 系统用户登录误选扩展 NLA／NTLM，保留 TLS 加密和系统密码校验。该配置作用于使用此默认注册表的 FreeRDP 服务端；已在 KRDP 6.7.5／FreeRDP 3.32.1 上验证协议协商。需要远程连接时，先用 `passwd` 为 `liveuser` 设置密码，再在 KDE 远程桌面设置中启用系统用户登录和服务。
- KDE 远程桌面使用 4K、16:9 虚拟显示器：用户服务覆盖配置以 `krdpserver --plasma --virtual-monitor 3840x2160@2` 启动，在连接时创建 3840×2160、200% 缩放（逻辑尺寸 1920×1080）的虚拟屏幕，实体显示器关闭或拔出后仍可提供画面。当前 Live 环境验证的虚拟输出为 60 Hz；实体屏幕开启时，虚拟屏幕作为额外输出。`/etc/skel/.config/kwinoutputconfig.json` 预设虚拟输出缩放为 2，避免 KWin 将其恢复为 100%；服务仍需按上述步骤启用。
- KRDP 虚拟屏幕鼠标定位临时修复：在 `/usr/local/lib/krdp-pointer-fix/` 随镜像携带带补丁的 `libKRdp.so.6`，仅远程桌面用户服务通过 `pointer-fix.conf` 加载，系统软件包原库保持原样。补丁初始化虚拟屏幕的逻辑尺寸，修复鼠标跳到角落和点击错位。此库固定基于 KRDP 6.7.5；启动前检查版本，其他版本会拒绝启动并提示重建或移除临时覆盖，避免加载不兼容的库。
- tty1 保留给 SDDM，屏蔽对应 getty；tty2 启用 root 自动登录救援终端，可通过 `Ctrl+Alt+F2` 切换。控制台、X11／SDDM 和 Plasma 用户模板均显式使用美式键盘布局。
- 预装 [Kamoso](https://apps.kde.org/kamoso/) 简易摄像头应用，可从应用菜单打开，支持拍照和录像。
- Fcitx5＋Rime 默认使用雾凇全拼 `rime_ice`，简体输出，`Ctrl+Space` 切换。KWin 在 Wayland 会话中启动输入法，禁用重复的桌面自启动；用户模板提供 Rime 推荐配置和 GTK XWayland 配置，设置 `XMODIFIERS`，不全局强制 GTK/Qt 输入模块。词库随镜像安装，首次登录自动部署，输入时无需联网。
- KDE 在接通电源、电池供电和低电量模式下均关闭空闲自动睡眠；通过 `/etc/skel/.config/powerdevilrc` 初始化 Live 用户设置，logind 同时设置 `IdleAction=ignore`。
- Plasma Wayland 首次登录时，`setup-live-display` 对当时已连接且启用的显示器设置“色彩配置文件：显示器内建”（EDID）和“色彩准确性：准确性优先”；仅修改这两项，成功后记录初始化标记，重新登录保留用户后续修改。显示器查询或设置失败会在最多约 30 秒内重试，失败不写标记，下次登录再尝试。后续热插拔的新显示器需在系统设置中单独调整。`kcminputrc` 的 Libinput 通用默认配置使用 Flat 曲线，关闭指针动态加速度，不绑定具体鼠标型号。
- `setup-live-user.service` 创建 UID 1000 用户、从镜像 `/etc/skel` 初始化其家目录，并设为空密码；SDDM 通过 `Requires` 和 `After` 等待它成功。
- 默认简体中文 `zh_CN.UTF-8`、美式键盘、默认 UTC，主机名 `archlive`。联网后使用内置 `ipiptimezone` 自动设置时区：通过 HTTPS 向 `ip.sb` 获取公网 IP，再查询镜像内的 IPv4／IPv6 数据库；出口代理或 VPN 可能影响定位结果。
- `live-timezone.service` 在 NetworkManager 连接成功或连通性变为 FULL 时异步触发；定时器开机 30 秒后补充检测，失败后每两分钟重试，每次最多 30 秒，不阻塞桌面启动。仅接受本机 tzdata 中有效的时区名，失败保留当前时区；成功后服务保持 active，本次启动不再自动改动，允许用户继续手动调整。
- NetworkManager 使用 wpa_supplicant 管理 Wi-Fi，通过 systemd-resolved 解析 DNS。屏蔽 systemd-networkd 及其 socket，取消模板的 iwd 自启动。
- 默认启用 `bluetooth.service`，显式安装 `bluez`、`bluez-utils`、`pipewire-audio`、`pipewire-pulse` 和 `wireplumber`。蓝牙名称为 `archlive`，设备类别固定为音响；所有手机传来的蓝牙音乐默认作为应用输入，供 AirPlayQt 等程序采集，详见下方“蓝牙音频采集”。
- 雷电（Thunderbolt）／USB4：两套内核的 initramfs 显式加入 `thunderbolt` 和 `thunderbolt_net`，提供控制器和雷电网络驱动；已有 `bolt` 软件包通过其 udev 规则在发现雷电设备时启动授权服务。可用 `boltctl list` 查看设备，`boltctl enroll <UUID>` 授权并登记设备；Live 环境的登记信息不跨重启保留。需要授权的设备遵循原有授权流程，详见 [Linux 内核文档](https://docs.kernel.org/admin-guide/thunderbolt.html)。
- `nvidia-open`、`nvidia-open-lts`、`nvidia-utils` 与 NVIDIA initramfs 模块、DRM modeset 参数保持配套。
- 保留 releng 安装／救援工具及服务，包括 SSH、cloud-init 和虚拟机来宾服务；这仍是临时 Live 环境。

zsh 默认配置由 `grml-zsh-config` 软件包提供，与原镜像一致；工程移植了美式 KDE 键盘配置，没有复制当前 `/home/liveuser`、账号令牌、Wi-Fi 连接或运行时状态。原有 `/mnt/sdc2/install.sh` 不参与本工程。

## 蓝牙音频采集

镜像固化以下配置，适用于 WirePlumber 0.5+：

- `/etc/bluetooth/main.conf` 设置 `Name=archlive`、`Class=0x000414`（音视频／扬声器）和 `AutoEnable=true`。服务类别位由 BlueZ 根据实际注册的音频服务添加，完整 Class 不必恰好等于 `0x000414`。
- `/etc/systemd/system/bluetooth.service.d/audio-receiver.conf` 禁用 BlueZ 的 `hostname` 插件，避免它按电脑机箱类型把音响类别覆盖回电脑；蓝牙名称使用上面的固定值，之后修改系统主机名不会自动同步它。
- `/etc/wireplumber/wireplumber.conf.d/51-bluetooth-input.conf` 匹配所有 `bluez_input.*`，设置 `bluez5.media-source-role=input`。手机音频作为采集输入出现，不自动播放到本地音箱；保留其他设备、系统默认输出、默认蓝牙角色及编码协商。应用仍需选择具体手机，规则不会把多台手机混音，也不强制 AAC 或采样率。

配置依据：[BlueZ main.conf](https://github.com/bluez/bluez/blob/master/src/main.conf)、[hostname 插件](https://github.com/bluez/bluez/blob/master/plugins/hostname.c)、[WirePlumber 蓝牙输入角色](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html#node-properties)。Arch 的 `pipewire-audio` 包包含蓝牙音频组件并依赖 AAC 库；KDE 蓝牙配对界面由 `plasma-meta` 依赖的 Bluedevil 提供。PipeWire 和 WirePlumber 在桌面用户会话中运行，不额外启动系统级音频服务。

新镜像启动后，在 KDE 蓝牙设置中打开“可被发现”，让手机配对 `archlive`，双方确认验证码，并将已配对手机设为信任。若使用终端，在同一个终端保持以下交互会话打开以处理验证码：

```text
bluetoothctl
power on
agent KeyboardDisplay
default-agent
pairable on
discoverable on
```

配对成功后在该会话输入 `trust 手机MAC地址`（替换为实际地址），然后可输入 `quit`。可被发现窗口为 180 秒，超时后可重新开启；设置超时不等于开机自动进入可被发现模式。若连上即断且日志出现 `a2dp.c:auth_cb() Access denied`，先检查手机是否已配对、信任以及 KDE 是否有待确认的授权提示。

在手机上播放音乐并将输出选为 `archlive`，再在采集程序中选择该手机。`wpctl status` 可查看输入，`bluetoothctl show` 可检查名称、类别及音频接收服务。若手机已连接却没有音频输入，先将手机输出切回手机自身，再选 `archlive` 并恢复播放；蓝牙传输处于 idle 时不一定有活动音频节点。

本次仅集成系统接收配置，AirPlayQt 程序及其 HomePod 设置需另行安装。镜像不包含手机 MAC、配对密钥、信任数据库或当前用户配置；没有持久化可写层时，重启后需重新配对，手机端可能需要先忽略旧的 `archlive` 配对记录。首次运行 AirPlayQt 时选择目标手机和 HomePod 组合。

## 增删包

直接修改 `configs/releng/packages.x86_64`：每行一个包名（官方仓库及预先准备的 AUR 包），可用空行和以 `#` 开头的整行注释，不使用行尾注释。分组只是便于阅读，不影响安装顺序。

初始 144 项清单来自当时的 `pacman -Qqe`，其中 `gparted` 是相对原始镜像新增的显式安装包。迁移时保留了旧工程后续新增的 `openai-codex`，当时共 145 项；后续加入中文桌面、输入法、时区依赖、VS Code、tk 和 Kamoso 等软件包，当前项数以 `check.sh` 输出为准。两个环境的原始包版本及显式包列表位于 `reference/`；它们用于对照，**不参与构建，也不锁定版本**。实际安装版本取决于构建当时的仓库。

`plasma-meta` 等元包会引入依赖；删除某个包名后，它仍可能因其他包依赖而被安装。若要精简 Plasma 的组件，需要将元包替换为选定的具体组件，同时调整检查器的桌面规则。不要把全部已安装依赖再次粘贴进清单。

普通应用只需调整包清单。涉及下列结构性修改时，需要同步配置，检查器会提示不一致：

- 删除 NVIDIA：同时删除两个驱动包、initramfs 配置中的 NVIDIA `MODULES` 和 `profiledef.sh` 中的 NVIDIA 内核参数。
- 删除桌面：调整 SDDM 服务链接、自动登录和默认 target；当前检查器以 `plasma-meta` 作为桌面基线，更换桌面需同步修改它。
- 更换内核：同步修改引导菜单、initramfs 和驱动包，并更新检查器的 Linux 内核约束。
- 删除由模板启动菜单或 systemd 单元引用的工具：同步调整对应菜单／服务。静态检查不覆盖所有包的服务依赖。

AUR 目前集成 `rime-ice-pinyin-git` 和 `visual-studio-code-bin`，通过下面的独立准备流程生成本地仓库；不在 Live 系统安装 AUR 助手。`tk` 通过官方仓库安装。新增 AUR 包需同时扩展 `build-aur.sh` 的构建列表和 `scripts/aur_repo.py` 的校验列表。持久化存储和额外安装器尚未配置，已有 `archinstall` 保留。

## 添加文件和修改镜像名称

把目标路径放在 `configs/releng/airootfs/` 下，例如 `configs/releng/airootfs/etc/skel/.config/` 为新用户提供默认设置。
定制 zsh 请使用 `configs/releng/airootfs/etc/skel/.zshrc.local`。不要预放入 `.zshrc`：该文件由 `grml-zsh-config` 安装，重复提供会让 pacman 报文件冲突。
不要复制整套宿主 `/etc` 或家目录。Archiso 默认将覆盖文件设为 root 所有、普通文件 0644、目录 0755；可执行脚本和 sudoers 等特殊权限必须登记到 `configs/releng/profiledef.sh` 的 `file_permissions`。

在 `profiledef.sh` 修改 `iso_name`、`iso_label`、`iso_publisher` 和 `iso_application`。
默认产物名称为 `archlinux-custom-YYYY.MM.DD-x86_64.iso`，日期来自构建时间；`SOURCE_DATE_EPOCH` 可指定日期来源，但不会固定仓库内容。更改菜单显示文字时，编辑 `syslinux/`、`grub/grub.cfg` 和 `grub/loopback.cfg`；`efiboot/` 中的旧 systemd-boot 菜单不参与当前构建。

### 自动时区资产

`/usr/local/bin/ipiptimezone` 链接到 `/usr/local/lib/ipiptimezone/ipiptimezone`，同目录包含实际的 `v4.ipdb`、`v6.ipdb` 文件，因为程序按可执行文件位置查找数据库。2026-09-30 从 `/mnt/sdc2/ipiplookup/bin/` 导入，复制时已解引用数据库链接，不依赖宿主路径；大小和 SHA-256 记录在 `reference/ipiptimezone.json`。两份数据库未压缩合计约 258 MiB，最终增加的 ISO 大小取决于 EROFS 压缩结果。

更新程序或数据库时，替换 `configs/releng/airootfs/usr/local/lib/ipiptimezone/` 中相应文件，并更新校验记录；保留程序执行权限和 `profiledef.sh` 的权限声明。运行时依赖 `curl`、`glibc`、`libgcc`、`libstdc++`、`tzdata` 以及 systemd；这些已由包清单和基础系统提供。公网 IP 获取仍需要联网，时区查询本身使用本地数据库。

`v4.ipdb` 和 `v6.ipdb` 是专有数据库，已加入 `.gitignore`，仅保留在本地用于构建，不得上传或强制加入 Git。新克隆工程后，需要自行将有权使用的两份数据库放回上述目录，配置检查通过后才能构建。

在新 Live 系统中检查或重新检测：

```bash
ipiptimezone                            # 只查询，不修改时区
timedatectl                             # 查看当前时区
journalctl -u live-timezone.service     # 查看检测日志
sudo systemctl restart live-timezone.service  # 手动重新检测并设置
```

若要关闭本次启动的自动检测并手动指定时区，可运行 `sudo systemctl mask --runtime --now live-timezone.service live-timezone.timer`，然后用 `sudo timedatectl set-timezone Asia/Shanghai` 等命令设置。集成修改不会更新已经生成的 ISO，需重新运行 `sudo ./build.sh`。

## 检查与构建

只检查本工程，不下载、不构建、不要求 root：

```bash
cd /mnt/sdc2/archiso
./check.sh
```

该命令检查 Shell 语法、包名格式和重复项、启动必需包、主要服务和驱动配置、特殊文件权限声明，并检查 GRUB 主菜单和 loopback 菜单中两套内核各自的普通、Copy to RAM 和语音辅助入口及对应启动参数。它会在独立 Bash 进程中加载 `profiledef.sh`；与 mkarchiso 一样，该文件属于可信的可执行配置。
静态检查不会查询在线仓库或验证包依赖能否解析，也不能证明镜像能启动。

本地仓库校验的失败场景可用 `python scripts/test_aur_repo.py` 测试：覆盖包缺失、损坏、错误包名／架构、索引不一致，以及发布失败保留旧仓库。这些测试不安装软件包、不修改宿主 pacman 配置。

实际构建前，在 x86_64 Arch Linux 宿主准备依赖：

```bash
sudo pacman -Syu --needed archiso python erofs-utils base-devel git grub
```

这会升级宿主并安装 Archiso 及其构建依赖。请确保宿主 `/etc/pacman.d/mirrorlist` 有启用的 HTTPS `Server`、网络可用，且 keyring 有效。构建检查要求 Archiso **91 系列**；若仓库提供更新版本，先审核对应 releng 和命令行兼容性，再更新 `reference/source.json` 的版本记录与检查规则，不要盲目降级宿主依赖。
EROFS 构建需要宿主的 `mkfs.erofs` 支持 LZMA；`./build.sh --check` 会检查此能力。镜像启动通过内核读取 EROFS，不要求 Live 系统安装 `erofs-utils`。
UEFI GRUB 构建需要宿主 `grub` 包提供的 `grub-mkstandalone`、x86_64 EFI 模块和 SBAT 文件；仅在 Live 包清单中包含 `grub` 不能代替宿主依赖。`./build.sh --check` 同时检查这些文件，并用 `grub-script-check` 检查两个 GRUB 菜单的语法，不生成引导程序或 ISO。

```bash
./build-aur.sh      # 普通用户：构建雾凇和 VS Code AUR 包；不要加 sudo
./build.sh --check  # 离线检查配置、宿主和必需的本地 AUR 包
sudo ./build.sh     # 安装官方包及本地 AUR 包，构建 ISO
```

`build-aur.sh` 每次显式运行都会获取两个包当时的 AUR 配方、雾凇上游源码和 VS Code 官方二进制，以普通用户执行 `makepkg --syncdeps`；缺少的官方构建依赖由 makepkg 通过 sudo 安装。此脚本不修改宿主语言、不安装输入法前端或构建出的 AUR 包。源码、产物和日志保存在 Git 忽略的 `localrepo/build-*` 中。两个包全部成功后，分别记录 AUR 提交、包版本、SHA-256，以及雾凇上游提交，并原子切换 `localrepo/current`；失败保留上一份可用仓库。已开始的 ISO 构建固定使用选定的仓库目录，不受后续切换影响。

`build.sh` 不调用 `build-aur.sh`，也不获取 AUR 源码。它在创建构建目录前校验目标包、架构、校验和及仓库索引；包缺失、损坏或索引不匹配会直接退出，提示运行 `./build-aur.sh`。`./check.sh` 仍可只做静态配置检查，`./check.sh --host --aur` 包含构建前全部检查。

本地 `[custom-aur]` 只加入每次构建生成的 pacman 配置，仅此仓库接受未签名的本地包；官方仓库继续要求签名，最终 Live 系统的 pacman 配置不包含宿主 `file://` 地址。无需把 AUR 包或源代码提交到 Git。构建完成后打印 ISO 字节数，超过当前 DVD 的 4,700,372,992 字节时报告错误并保留产物，不自动删包，也不刻录。

每次构建创建独立的 `work/build-时间-随机后缀/` 和对应 `out/build-时间-随机后缀/`，后者保存 ISO 与 `build.log`。
这样包清单修改后不会复用旧 rootfs，也不会覆盖同一天的 ISO。构建失败会返回非零状态并保留日志和工作目录，便于排查。
构建入口使用 util-linux 的 `script` 保留终端，让 pacman 显示下载进度，同时实时保存 `build.log` 并传递构建退出状态。日志包含终端进度刷新控制字符，可用 `less -R` 查看。

下载的软件包统一缓存到工程内的 `work/cache/pacman/pkg/`，每次构建共用；版本相同且缓存有效时无需重新下载，新增或升级的包仍需下载。脚本按工程的实际路径生成每次构建的 `build.pacman.conf`，通过 `mkarchiso -C` 指定缓存位置，不修改宿主配置。缓存位于 rootfs 外，不会打进 ISO，也不会在构建结束时自动清理。`work/` 已被 Git 忽略。

每次构建仍重新安装 rootfs、生成 initramfs 和压缩镜像；下载缓存不等于增量构建。清理某个 `work/build-*` 目录不会影响共享缓存；删除整个 `work/` 会同时删除缓存。按当前包清单，首轮软件包缓存约需 2.4 GB，保留多个版本时会继续增长。
脚本不会安装宿主依赖、重新导出包清单、删除旧目录或自动重试。工作目录较大；清理前确认构建已退出且没有残留挂载，再手动处理明确不需要的目录。工程所在分区需要可写，构建过程需要 root 和挂载能力；受限沙箱内仅执行检查。

## 后续启动验收

包清单确定并成功构建后，再分别验证 BIOS、UEFI 启动，KDE 自动登录、终端 sudo、DNS、有线网络与 Wi-Fi。
切换 UEFI GRUB 后，应分别验证两套内核的普通／Copy to RAM 入口，并覆盖 U 盘直写、光盘和 Ventoy 启动。构建后还应检查 EFI FAT 分区不再含内核／initramfs，而 ISO 的 `/arch/boot/x86_64/` 中仍包含完整的两套启动文件。
QEMU 普通显示设备测试不能代替实体 NVIDIA 显卡测试；还需在目标硬件确认驱动和 Plasma 会话。当前通过 Ventoy 启动原镜像的事实不代表新镜像已验证兼容，Ventoy 也留待实机测试。


## Git 分支与上游同步

本目录由 `git clone --origin upstream https://github.com/archlinux/archiso.git` 创建，保留完整官方历史。
当前定制分支为 `master`；官方模板的修改直接位于 `configs/releng/`，因此 Git 可以按共同祖先合并。
上游工具源码、`configs/baseline/` 以及 `README.rst` 仍保留。releng 的 `packages.aarch64` 与 `bootstrap_packages` 也保留供上游同步，但本工程的 x86_64 ISO 构建不使用它们。原独立骨架 `/mnt/sdc2/archlive/` 留作备份；之后在本目录继续编辑。

开始同步前，先提交本地包清单和配置修改，确保 `git status --short` 没有输出。然后执行：

```bash
git switch master
git fetch upstream --tags
git merge upstream/master
./check.sh
./build.sh --check
```

如需按发布版升级，将合并命令换成 `git merge v92`（示例版本；使用实际存在的目标 tag）。
有冲突时，编辑冲突文件保留需要的两边改动，然后 `git add <已解决的文件>`、`git merge --continue`。
若要放弃尚未完成的合并，执行 `git merge --abort`。不要直接用上游文件覆盖整套 releng 配置。

重点审查 `configs/releng/packages.x86_64`、`profiledef.sh`、initramfs、引导菜单和网络服务。
Git 能合并文本，不会判断上游新增包是否适合你的镜像，也不会保证驱动和服务仍兼容。
合并新 Archiso 版本后，核对工具与模板变化，更新 `reference/source.json` 中的版本、提交和归档记录，再运行检查和构建／启动验证。
当前构建入口使用宿主安装的 `mkarchiso`，并不直接运行仓库内的开发版本；其版本需与审核后的模板匹配。

自定义仓库远程 `origin` 已配置为：

```text
git@github.com:z8kh8E6t-rEv62qT7/archiso_custom_build.git
```

`master` 保存定制内容并跟踪 `origin/master`；本地临时分支已删除。
`upstream` 保留官方仓库地址，用于获取和合并官方更新。后续提交自己的修改后，执行：

```bash
git push origin master
```

## 重建或移除 KRDP 临时鼠标修复

镜像已包含编译完成的修复库，普通 ISO 构建无需再编译 KRDP。源码固定为 KDE KRDP `v6.7.5`（提交 `270dcf01851229134f74fa7d90ac338ec788ec67`），补丁、上游许可文本和 SHA-256 记录均位于 `configs/releng/airootfs/usr/local/lib/krdp-pointer-fix/`。对应已推送的修复提交为 [117b6b7](https://invent.kde.org/ldai/krdp/-/commit/117b6b7703725e581c043af71c5b2df2129bc5ab)。

需要重建时，在安装 KRDP 6.7.5 及其开发依赖的 x86_64 Arch 宿主上，以普通用户运行：

```bash
sudo pacman -S --needed base-devel git cmake ninja extra-cmake-modules plasma-wayland-protocols
./scripts/build-krdp-pointer-fix.sh
./check.sh
```

脚本验证源码提交，应用随附补丁，仅编译 KRdp 库，再更新镜像内库和校验记录。构建目录保留在 `${TMPDIR:-/tmp}/archiso-krdp-pointer-fix-*`；不安装到宿主系统，也不自动构建 ISO。更换 KRDP 版本时需重新审核补丁、源码版本和依赖后重建，不能直接沿用此 6.7.5 库。

上游发行版包含修复后，移除镜像中的 `pointer-fix.conf`、`check-krdp-pointer-fix` 和私有库目录，并同步移除 `profiledef.sh` 权限项、检查器 `check_pointer_fix()` 及本重建脚本。保留 `virtual-monitor.conf` 即可继续使用 4K、200% 虚拟屏幕。
