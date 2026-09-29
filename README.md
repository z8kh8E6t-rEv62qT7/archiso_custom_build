# 自定义 Arch Linux Live ISO

基于官方 Git 历史的可编辑 Archiso 工程，参照当前 `archlinux-kde-nvidia` Live 环境。
**尚未构建／启动验证**。当前仅完成配置、构建入口和静态检查，没有下载镜像所需的整套软件包。

## 工程入口

| 路径 | 用途 |
| --- | --- |
| `configs/releng/packages.x86_64` | 唯一安装包清单，迁移时共 145 项（含新增的 openai-codex） |
| `configs/releng/profiledef.sh` | 名称、日期版本、架构、启动模式、压缩和文件权限 |
| `configs/releng/airootfs/` | 映射到新镜像根目录的文件覆盖 |
| `configs/releng/pacman.conf` | 构建镜像时使用的官方 core、extra 仓库配置 |
| `configs/releng/efiboot/`、`configs/releng/syslinux/` | UEFI 和 BIOS 启动配置 |
| `configs/releng/grub/` | 官方模板附带的 GRUB loopback 配置 |
| `check.sh`、`build.sh` | 检查入口、构建入口 |
| `reference/` | 模板来源、官方说明和两个环境的包快照 |
| `work/`、`out/` | 实际构建时才创建；分别保存工作数据和 ISO／日志 |

定制初始基线为官方 [Archiso v91](https://github.com/archlinux/archiso/tree/v91/configs/releng)，提交
`723da192226e1c9d5def9168f13332793c82a85e`。来源及下载归档的 SHA-256 记录在
`reference/source.json`；官方 profile 说明保存在 `reference/README.profile.upstream.rst`。
保留上游 GPL-3.0-or-later 许可，见 `LICENSE`。

## 当前行为

- x86_64、Linux 内核、BIOS Syslinux 与 UEFI systemd-boot 启动，根文件系统使用 squashfs。
- KDE Plasma，SDDM 自动登录 `liveuser`，zsh，`liveuser` 免密 sudo。
- `setup-live-user.service` 创建 UID 1000 用户、从镜像 `/etc/skel` 初始化其家目录，并设为空密码；SDDM 通过 `Requires` 和 `After` 等待它成功。
- 英文 `C.UTF-8`、美式键盘、UTC，主机名 `archlive`。
- NetworkManager 使用 wpa_supplicant 管理 Wi-Fi，通过 systemd-resolved 解析 DNS。屏蔽 systemd-networkd 及其 socket，取消模板的 iwd 自启动。
- `nvidia-open`、`nvidia-utils` 与 NVIDIA initramfs 模块、DRM modeset 参数保持配套。
- 保留 releng 安装／救援工具及服务，包括 SSH、cloud-init 和虚拟机来宾服务；这仍是临时 Live 环境。

只移植了原镜像的 zsh 默认配置及美式 KDE 键盘配置；没有复制当前 `/home/liveuser`、账号令牌、Wi-Fi 连接或运行时状态。原有 `/mnt/sdc2/install.sh` 不参与本工程。

## 增删包

直接修改 `configs/releng/packages.x86_64`：每行一个官方仓库包名，可用空行和以 `#` 开头的整行注释，不使用行尾注释。分组只是便于阅读，不影响安装顺序。

初始 144 项清单来自当时的 `pacman -Qqe`，其中 `gparted` 是相对原始镜像新增的显式安装包。迁移时保留了旧工程后续新增的 `openai-codex`，目前共 145 项。两个环境的原始包版本及显式包列表位于 `reference/`；它们用于对照，**不参与构建，也不锁定版本**。实际安装版本取决于构建当时的仓库。

`plasma-meta` 等元包会引入依赖；删除某个包名后，它仍可能因其他包依赖而被安装。若要精简 Plasma 的组件，需要将元包替换为选定的具体组件，同时调整检查器的桌面规则。不要把全部已安装依赖再次粘贴进清单。

普通应用只需调整包清单。涉及下列结构性修改时，需要同步配置，检查器会提示不一致：

- 删除 NVIDIA：同时删除两个驱动包、initramfs 配置中的 NVIDIA `MODULES` 和 `profiledef.sh` 中的 NVIDIA 内核参数。
- 删除桌面：调整 SDDM 服务链接、自动登录和默认 target；当前检查器以 `plasma-meta` 作为桌面基线，更换桌面需同步修改它。
- 更换内核：同步修改引导菜单、initramfs 和驱动包，并更新检查器的 Linux 内核约束。
- 删除由模板启动菜单或 systemd 单元引用的工具：同步调整对应菜单／服务。静态检查不覆盖所有包的服务依赖。

AUR、本地包仓库、持久化存储和额外安装器尚未配置。已有包清单中的 `archinstall` 仍保留。

## 添加文件和修改镜像名称

把目标路径放在 `configs/releng/airootfs/` 下，例如 `configs/releng/airootfs/etc/skel/.config/` 为新用户提供默认设置。
不要复制整套宿主 `/etc` 或家目录。Archiso 默认将覆盖文件设为 root 所有、普通文件 0644、目录 0755；可执行脚本和 sudoers 等特殊权限必须登记到 `configs/releng/profiledef.sh` 的 `file_permissions`。

在 `profiledef.sh` 修改 `iso_name`、`iso_label`、`iso_publisher` 和 `iso_application`。
默认产物名称为 `archlinux-custom-YYYY.MM.DD-x86_64.iso`，日期来自构建时间；`SOURCE_DATE_EPOCH` 可指定日期来源，但不会固定仓库内容。更改菜单显示文字时，也需编辑 `efiboot/`、`syslinux/` 和 `grub/`。

## 检查与构建

只检查本工程，不下载、不构建、不要求 root：

```bash
cd /mnt/sdc2/archiso
./check.sh
```

该命令检查 Shell 语法、包名格式和重复项、启动必需包、主要服务和驱动配置、特殊文件权限声明。它会在独立 Bash 进程中加载 `profiledef.sh`；与 mkarchiso 一样，该文件属于可信的可执行配置。
静态检查不会查询在线仓库或验证包依赖能否解析，也不能证明镜像能启动。

实际构建前，在 x86_64 Arch Linux 宿主准备依赖（**本次未执行**）：

```bash
sudo pacman -Syu --needed archiso python
```

这会升级宿主并安装 Archiso 及其构建依赖。请确保宿主 `/etc/pacman.d/mirrorlist` 有启用的 HTTPS `Server`、网络可用，且 keyring 有效。构建检查要求 Archiso **91 系列**；若仓库提供更新版本，先审核对应 releng 和命令行兼容性，再更新 `reference/source.json` 的版本记录与检查规则，不要盲目降级宿主依赖。

```bash
./build.sh --check   # 检查配置、宿主工具和 Archiso 版本；普通用户可运行
sudo ./build.sh     # 只有此命令开始下载软件包并构建 ISO
```

每次构建创建独立的 `work/build-时间-随机后缀/` 和对应 `out/build-时间-随机后缀/`，后者保存 ISO 与 `build.log`。
这样包清单修改后不会复用旧 rootfs，也不会覆盖同一天的 ISO。构建失败会返回非零状态并保留日志和工作目录，便于排查。
脚本不会安装宿主依赖、重新导出包清单、删除旧目录或自动重试。工作目录较大；清理前确认构建已退出且没有残留挂载，再手动处理明确不需要的目录。工程所在分区需要可写，构建过程需要 root 和挂载能力；受限沙箱内仅执行检查。

## 后续启动验收

包清单确定并成功构建后，再分别验证 BIOS、UEFI 启动，KDE 自动登录、终端 sudo、DNS、有线网络与 Wi-Fi。
QEMU 普通显示设备测试不能代替实体 NVIDIA 显卡测试；还需在目标硬件确认驱动和 Plasma 会话。当前通过 Ventoy 启动原镜像的事实不代表新镜像已验证兼容，Ventoy 也留待实机测试。


## Git 分支与上游同步

本目录由 `git clone --origin upstream https://github.com/archlinux/archiso.git` 创建，保留完整官方历史。
当前定制分支为 `codex/custom-live`；官方模板的修改直接位于 `configs/releng/`，因此 Git 可以按共同祖先合并。
上游工具源码、`configs/baseline/` 以及 `README.rst` 仍保留。releng 的 `packages.aarch64` 与 `bootstrap_packages` 也保留供上游同步，但本工程的 x86_64 ISO 构建不使用它们。原独立骨架 `/mnt/sdc2/archlive/` 留作备份；之后在本目录继续编辑。

开始同步前，先提交本地包清单和配置修改，确保 `git status --short` 没有输出。然后执行：

```bash
git switch codex/custom-live
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

本地克隆不等于已经创建 GitHub Fork。要推送到自己的 GitHub 仓库，可以在 GitHub 创建官方仓库的 Fork，或创建空仓库，然后配置自己的远程：

```bash
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin codex/custom-live
```

将自己仓库的默认分支设为 `codex/custom-live`，便于直接看到定制内容。
`upstream` 始终用于获取官方更新，`origin` 指向你自己的仓库；本次没有创建远程仓库或推送。
