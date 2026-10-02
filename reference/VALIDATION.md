# 骨架验证记录

## 蓝牙音频采集配置（2026-10-02）

- 显式加入 `pipewire-audio`、`pipewire-pulse`、`wireplumber`，复用已有 BlueZ 服务启用链接和 KDE Bluedevil 配对界面。
- BlueZ 固定名称 `archlive` 和音响类别 `0x000414`，自动启用适配器；通过 systemd drop-in 禁用会覆盖名称／设备类别的 `hostname` 插件。配对仍需用户确认，发现窗口为 180 秒。
- WirePlumber 系统规则将所有 `bluez_input.*` 的媒体源角色设为 `input`，供应用采集；不写入手机地址、配对密钥或信任数据库，不自动将音频输出到本地音箱。
- `./check.sh`、`./build.sh --check`（含宿主和本地 AUR 仓库校验）通过。
- 使用 PipeWire 原生 `spa-json-dump` 解析新增 WirePlumber 片段成功；使用 overlay 和宿主 unit 搜索路径运行 `systemd-analyze --man=no verify bluetooth.service` 通过；`git diff --check` 通过。
- 当前桌面此前已验证 iPhone AAC → PipeWire → AirPlayQt → HomePod 有声；这是原来的单手机规则和运行时设备类别下的验证，不能代替新镜像中全设备规则与 BlueZ 启动配置的验证。
- 本次未重新构建 ISO、未重启当前蓝牙／音频服务，也未将 AirPlayQt 程序打包进镜像。新镜像启动、iPhone 发现／配对、全设备采集以及重启后设备类别保持仍待实机验收。

2026-09-29，初始骨架验证记录；下述 144 项指初始快照。

- `./check.sh`：通过，144 个显式包；包名集合与当前会话快照完全一致，相对原始镜像新增 `gparted`。
- Shell `bash -n` 和 Python 语法编译：通过。宿主没有 ShellCheck，本次未运行 ShellCheck。
- 在临时工程副本中验证：重复包、缺少 Linux 启动包、NVIDIA 包不成对、缺少 NVIDIA 模块、缺少 SDDM 包、用户初始化依赖缺失、残留 iwd 自启动，均被正确拒绝。
- `systemd-analyze --man=no verify setup-live-user.service sddm.service`：使用工程 overlay 与宿主 `/usr/lib/systemd/system` 的 unit 搜索路径，通过。此检查依赖当前宿主单元和可执行文件，不能代替未来镜像内验证。
- `build.sh --help` 正常退出，未知参数返回 2。
- `build.sh --check` 及无参数调用：按预期报告未安装 Archiso，返回 1，没有下载软件包或创建 `work/`、`out/`。

**尚未构建／启动验证**。没有执行仓库包可用性查询、完整依赖解析、ISO 构建、BIOS／UEFI／Ventoy 启动或实体 NVIDIA 驱动测试。


## 官方仓库布局迁移

- 保留原工程迁移前的完整配置，包括后来添加的 `openai-codex`；迁移后包清单共 145 项。
- 原 `profile/` 的文件内容、符号链接和权限均完整迁移；额外保留上游未使用的 `packages.aarch64` 和 `bootstrap_packages`，以减少后续合并冲突。当前 profile 仍明确指定 x86_64、ISO-only。
- 构建和检查入口已改为使用 `configs/releng/`；原始包快照保留历史内容，不用迁移时的宿主重新导出。
- 官方历史保留；迁移时使用 `codex/custom-live` 临时分支，后按用户要求将提交移至 `master` 并删除临时分支。
- 迁移后的 `./check.sh`、`./build.sh --check` 均通过；验证时宿主已提供 Archiso 91-1。
- 新增入口通过 ShellCheck；因宿主没有 make，直接运行 Makefile check 目标同一组脚本的 ShellCheck 检查，通过。
- 本次未运行构建，未生成 work/ 或 out/。

## 旧构建目录对比补全（2026-09-30 UTC）

对照 `/mnt/nbd0p1/archiso-kde-nvidia/`（Archiso 90 profile）与本工程
`configs/releng/`（基于 Archiso 91），检查普通文件、隐藏文件及符号链接。
同时核对旧目录 README 和构建专用 pacman 配置；未复制缓存、构建 rootfs 或旧 ISO。

- 旧 profile 的 143 个包均已包含在当前清单中；检查时当前共 190 项，新增 47 项，无缺失包。保留工作区已有的包清单修改。
- 恢复旧配置的终端安排：屏蔽 `getty@tty1.service`，将 root 自动登录配置移至 tty2，并添加 `getty.target.wants/getty@tty2.service` 启用链接，tty1 留给 SDDM。
- 恢复 `etc/X11/xorg.conf.d/00-keyboard.conf`，与已有控制台和 Plasma 的美式键盘配置一致。
- 为 Syslinux 的 NBD、NFS、HTTP 三个 PXE 模板入口补回 `cow_spacesize=4G`，保留当前 NVIDIA 参数占位符。
- 检查器新增终端安排、X11／Plasma 键盘配置及所有 Live 启动模板的可写层参数检查。

以下差异保留当前实现：

| 旧配置 | 当前处理及依据 |
| --- | --- |
| `etc/mkinitcpio.d/linux.preset` | 不恢复。上游提交 `67c79b0` 删除此文件，说明默认 preset 已满足需要；当前两套内核通过 `mkinitcpio.conf.d/archiso.conf` 配置。 |
| `etc/modprobe.d/broadcom-wl.conf` | 不恢复。上游提交 `c66a6ec` 删除此覆盖文件；当前和旧包清单都不包含 `broadcom-wl`。 |
| `20-live-user.hook` 及旧用户创建脚本 | 保留启动时的 `setup-live-user.service` 和 SDDM 依赖关系，从最终 `/etc/skel` 初始化用户。 |
| `NetworkManager/conf.d/10-dns.conf` | 其 `dns=systemd-resolved` 已包含在 `10-live.conf` 中，同时保留 wpa_supplicant 后端。 |
| SquashFS、单内核、默认英文、旧镜像名 | 保留当前 EROFS、双内核、中文桌面、输入法、自动时区、蓝牙、雷电和镜像命名。 |
| 构建专用 Fastly／USTC pacman 配置 | 保留当前宿主 mirrorlist 和工程内共享缓存机制，不引入旧 `/mnt/sda1` 路径或旧镜像优先级。 |
| `plasmalogin.conf.d/` | 旧目录为空，当前使用 SDDM，无需迁移。 |

验证结果：`./build.sh --check` 通过（配置、宿主和本地 AUR 仓库）；
`systemd-analyze --man=no verify getty@tty2.service sddm.service` 在工程 overlay
与宿主 unit 搜索路径下通过；`git diff --check` 通过。
此次仅补全配置，未重新构建 ISO，未进行启动或硬件验证；已有 ISO 不包含这些修改。

## initramfs 压缩优化（2026-09-30 UTC）

在旧构建 `work/build-20260930T053255Z-h2oh3Z/` 的 rootfs 中，用只读
Bubblewrap 环境分别生成两套测试 initramfs，保持原 MODULES、HOOKS 和
XZ `-9e`，仅新增 `MODULES_DECOMPRESS="yes"`。使用镜像内的 mkinitcpio 42.1，
测试文件及日志保存在 `work/initramfs-compression-check/`，未覆盖旧 ISO。

| 内核 | 原 initramfs 字节数 | 优化后字节数 | 减少字节数 |
| --- | ---: | ---: | ---: |
| linux 7.2.7-arch1-1 | 333657156 | 284788032 | 48869124 |
| linux-lts 6.18.54-1-lts | 328882256 | 280802868 | 48079388 |

两套合计减少 96948512 字节（92.46 MiB）。BIOS 文件区与 UEFI FAT 镜像各保存
一份，按旧镜像布局预计总计减少约 184.91 MiB，最终 ISO 大小另以完整构建为准。

- 解包并比较两套 initramfs：将模块和固件的压缩后缀及对应链接规范化后，
  对所有普通文件的解压内容计算 SHA-256，并比较文件权限和符号链接。
  主内核比较 3393 项，LTS 比较 3359 项，均无文件缺失或额外文件。
- 比较排除内嵌 `buildconfig` 和重新生成的二进制路径索引 `modules.dep.bin`；
  initramfs 只保留二进制依赖索引，不包含文本 `modules.dep`。
  重建用的是已完成定制的 rootfs，因此 `usr/lib/os-release` 多出已核实的
  `IMAGE_ID=archlinux-custom` 和 `IMAGE_VERSION=2026.09.29`；去掉这两行后内容一致。
  其余比较项全部一致，结果见测试目录 `content-comparison.json` 与 `verify-content.py`。
- 固件缺失警告与原构建相同，没有本次新增的缺失项。
- `modprobe --show-depends` 对两套解包目录中的 `nvidia_drm` 均成功，未加载宿主模块。
- 对优化后主内核的 1479 个模块和 LTS 的 1474 个模块逐一执行
  `modprobe --show-depends`，均成功，返回的所有 insmod 文件路径均存在。
- 主内核 early CPIO 从 229.49 MiB 降到 17.19 MiB；主 CPIO 解压体积从
  176.62 MiB 增到 777.33 MiB。启动早期内存需求增加；这不是进程实际峰值内存测量。
- 已将开关加入 profile，并增加静态检查，保留双内核及原有软件包。

完整重建使用 `work/build-20260930T055617Z-qMJUh1/`。与旧镜像相比，
当前包清单的 `qemu-img`、`qemu-tools` 及依赖 `qemu-common` 一并纳入；
仓库中的 `f2fs-tools` 从 1.16.0-4 升至 1.17.0-1，没有删除原有包。
因此最终 ISO 的净变化还包含这些变化，不应全部归因于 initramfs 压缩。
正式构建的主内核 initramfs 为 284798552 字节，LTS 为 280797240 字节；
两者内嵌配置均确认启用了 `MODULES_DECOMPRESS="yes"`。

完整构建成功，产物为
`out/build-20260930T055617Z-qMJUh1/archlinux-custom-2026.09.29-x86_64.iso`，
大小 4578738176 字节（4366.625 MiB），相比旧 ISO 的 4766859264 字节
减少 188121088 字节（179.40625 MiB，3.95%）。当前 DVD 容量为
4700372992 字节，剩余 121634816 字节（116 MiB），构建入口容量检查通过。

- `./build.sh --check`、完整 `sudo ./build.sh` 均通过。
- UEFI FAT 镜像通过 `fsck.fat -n`；其中两套内核和 initramfs 共四个文件的
  SHA-256 与 ISO 文件区的构建输入一致。
- 对最终 ISO 使用 xorriso 检查，BIOS 和 UEFI 的 El Torito 引导项均存在，
  附加 EFI 分区和 GPT／MBR 引导结构均已生成。
- 根据 ISO 内 EROFS 的 LBA 292782，直接执行
  `fsck.erofs --extract --offset=599617536 <ISO>`，全部文件解码及文件系统完整性检查通过；
  未向磁盘另行解包。最终 ISO 的 SHA-256 为
  `2839d733f3ab8eeb151736e91b47775c3c6868acd824359f398c636d2dc68aec`，
  同目录已保存 `.iso.sha256` 校验文件。
- 没有进行实际启动验证；本次没有删除旧 ISO、软件包或备用内核。

## UEFI 改用 GRUB，共用启动文件（2026-09-30，仅配置）

- `profiledef.sh` 的启动模式改为 `bios.syslinux` 和 `uefi.grub`。
  使用宿主 Archiso 91 的原生实现：EFI FAT 镜像只复制 GRUB 引导程序与
  UEFI Shell，GRUB 定位 ISO 卷后加载 ISO 文件区中的内核和 initramfs；
  不调用 systemd-boot 模式中复制内核到 FAT 的步骤，无需修改 mkarchiso。
- 复用现有 `grub/grub.cfg` 与 `grub/loopback.cfg`，保留两套内核的普通、
  Copy to RAM、语音辅助入口，以及默认普通启动、15 秒等待、
  `cow_spacesize=4G` 和 NVIDIA 参数。BIOS 继续使用 Syslinux。
- 保留旧 `efiboot/` 模板供上游同步，当前构建和检查不再使用它；文档明确
  旧 ISO 及其体积测量不包含这次引导切换。
- 配置检查改为要求 GRUB 主菜单与 loopback 菜单，检查六个入口的唯一性、
  内核／initramfs 配对、启动模式和定位参数。宿主检查新增
  `grub-mkstandalone`、`grub-script-check`、x86_64 EFI 模块及 SBAT 文件。
  README 宿主依赖命令补充 `grub`。
- `./build.sh --check` 通过（190 项包清单、宿主和 AUR 仓库），两个菜单的
  原始模板及替换占位符后的 GRUB 语法检查均通过，`git diff --check` 通过。
- 在临时目录中分别验证两个菜单：正常菜单通过；缺失 LTS 入口、错误的
  initramfs 配对、错误的 Copy to RAM 模式、缺失内核参数、错误默认入口、
  缺失根文件系统定位参数这六类变更均被检查器拒绝。

遵照用户要求，此次未执行 ISO 构建、未生成新的 EFI 引导程序、未更改旧产物。
实际体积收益、BIOS／UEFI／Ventoy 及实体硬件启动需待用户重新构建后验证。

## KRDP 系统用户认证兼容修复（2026-10-02）

- 当前 Live 环境为 KRDP 6.7.5-1、FreeRDP 2:3.32.1-1。`liveuser` 存在且已启用系统用户认证，但客户端请求扩展认证时会选中 HYBRID_EX（协议值 8），随后报 `Could not find user in SAM database`，尚未进入系统密码校验。
- 新增 `configs/releng/airootfs/etc/FreeRDP/FreeRDP/HKLM.reg`，在 `HKEY_LOCAL_MACHINE\Software\FreeRDP\FreeRDP\Server` 中设置 `ExtSecurity=0`，与当前 Live 环境已应用的配置逐字一致。文件权限为 0644，由 Archiso 默认以 root 所有者安装。此项影响使用该默认注册表的 FreeRDP 服务端。
- 当前 Live 环境重启 KRDP 后，用协议掩码 1、3、11 分别进行协商，均返回 TLS（协议值 1）；三次 TLS 握手均成功，使用 TLS 1.3／TLS_AES_256_GCM_SHA384。系统密码认证保留，实际客户端登录尚待确认。
- `./check.sh`（190 项包清单）、`git diff --check` 通过。此次未构建或启动新 ISO；用户仍需为新 Live 系统的 `liveuser` 设置密码，并在 KDE 设置中启用系统用户远程登录和服务。
