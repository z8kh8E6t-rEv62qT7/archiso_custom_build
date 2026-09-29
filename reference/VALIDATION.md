# 骨架验证记录

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
- 官方历史保留，定制分支为 `codex/custom-live`，只在本地提交，未推送。
- 迁移后的 `./check.sh`、`./build.sh --check` 均通过；验证时宿主已提供 Archiso 91-1。
- 新增入口通过 ShellCheck；因宿主没有 make，直接运行 Makefile check 目标同一组脚本的 ShellCheck 检查，通过。
- 本次未运行构建，未生成 work/ 或 out/。
