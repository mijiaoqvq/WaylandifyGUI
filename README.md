# WaylandifyGUI

面向 Arch Linux + niri + Wayland 的 GTK4 应用启动参数管理工具，使用 Python / PyGObject。

## 运行

```sh
sudo pacman -S --needed python python-gobject gtk4 desktop-file-utils
cd WaylandifyGUI
./waylandify-gui
```

也可以在源码目录执行 `python -m waylandify_gui`。使用系统 Python，不需要 pip 或虚拟环境。GTK4 会根据桌面会话选择后端；需要明确指定时可运行 `GDK_BACKEND=wayland ./waylandify-gui`。

## 安装

用户级安装（不需要 sudo）：

```sh
./install.sh
```

随后从应用启动器搜索 WaylandifyGUI，或运行 `~/.local/bin/waylandify-gui`。脚本在启动项中写入绝对路径，不依赖启动器的 PATH。可使用 `PREFIX=/绝对路径 ./install.sh` 指定安装前缀；这只影响本工具的安装位置，应用覆盖仍固定写入 `~/.local/share/applications`。

也可在源码目录生成本地源码归档，再构建并安装系统包：

```sh
python tools/make-release.py
makepkg -si
```

安装后的命令为 `waylandify-gui`，系统包名为 `waylandify-gui`。正式 AUR 发布步骤见 [PACKAGING.md](PACKAGING.md)。

## 改名与兼容

1.1.0 将应用名改为 **WaylandifyGUI**。程序是独立实现，不是 [jassielof/waylandify](https://github.com/jassielof/waylandify) 命令行项目的前端，也不依赖它。命令、Python 模块、应用 ID 和安装路径已使用独立名称。

为继续恢复 1.0.0 创建的覆盖，备份目录仍保留 `${XDG_STATE_HOME:-~/.local/state}/waylandify/`；不自动迁移或删除旧备份。旧版若通过 `install.sh` 安装，旧启动项可能仍显示，可手动移除旧版启动项与程序文件，但请保留状态目录。此包不声明替换或冲突于其他同名项目。

## 使用

1. 启动后自动递归扫描 `/usr/share/applications` 和 `~/.local/share/applications`，按 desktop ID 合并，同 ID 的用户文件优先。显示本地化名称和主题图标，绝对图标路径也受支持。
2. 输入名称、desktop ID 或 Exec 内容实时筛选。选择应用后查看原始命令、当前命令、预览和文件位置。
3. 点击「启用 Wayland」：在可执行文件后加入 `--ozone-platform=wayland`；若有 `--ozone-platform=x11` 或其他取值则替换，保留引号及 `%U` 等占位符。支持普通命令和 `env KEY=value app`。
4. 自动运行 `update-desktop-database ~/.local/share/applications`。完全退出目标应用后重新打开即可使用新命令；数据库刷新失败会单独显示，已写入的文件仍可恢复。
5. 点击「恢复默认」：原本存在用户文件则按备份逐字节恢复，包括原权限；原本只有系统文件则删除覆盖，让最新系统文件生效。随后再次刷新数据库。

工具不执行被扫描的 Exec，不修改 `/usr/share/applications` 中的文件。扫描和文件操作在后台线程执行；写入期间禁用操作按钮并阻止关闭窗口。

## 覆盖与备份

- 完整复制原 desktop 文件，仅改变 `[Desktop Entry]` 内的主 `Exec`。注释、本地化名称、图标、MIME 类型及 `[Desktop Action ...]` 快捷操作保留；快捷操作命令不会随主命令修改。
- 当 `DBusActivatable=true` 时，用户覆盖会设置为 `false`，使启动器使用修改后的 Exec。恢复时同步还原。
- 已有用户文件会先备份。记录位于 `${XDG_STATE_HOME:-~/.local/state}/waylandify/`，每个应用一个 JSON，权限为 0600；含原始内容、目标路径、权限和修改后内容的 SHA-256。保存记录时不依赖 desktop 文件里的自定义标记。
- 参数已存在但没有 WaylandifyGUI 备份时，显示「已存在」，禁用重复应用与恢复，避免误删原有设置。
- 检测到覆盖文件被外部改动时，保留备份并停止自动恢复。请手动比较 JSON 中 Base64 编码的 `before`（原用户文件，null 表示原本不存在）和 `source`（修改时源文件）。确认处理后才能删除相应记录。
- 使用进程锁串行化本工具写入，临时文件加原子替换避免部分写入。若进程在备份与覆盖写入之间被强制终止，可能留下未完成记录，后续会保守显示冲突；不会自动覆盖当前文件。
- 删除用户覆盖或修改安装路径后，可能留下未被扫描到的备份记录，需要手动清理。不要在仍需恢复应用时删除状态目录。

## 边界

`--ozone-platform=wayland` 适用于支持 Ozone 的 Chromium / Electron 应用，并不适用于所有 GUI 应用。工具展示可扫描的 Application 项，包含 NoDisplay 项，忽略被 Hidden 项隐藏的未管理应用以及缺少 Exec 的项目。

对于 shell `-c`、Flatpak、Snap、解释器及已知间接启动命令，禁用自动编辑并说明原因。其他自定义启动脚本是否转发参数需要用户确认。带选项的 `env` 暂不支持。用户级符号链接不会被改写；desktop ID 冲突、不可读文件、损坏备份会显示扫描提示。

用户覆盖优先于后续系统包更新，因此系统应用更新后如需同步新 desktop 内容，可先恢复再重新启用。工具仅扫描需求指定的两个目录，不扫描 Flatpak 导出目录或其他 XDG_DATA_DIRS。

## 测试

```sh
python -m unittest discover -s tests -v
desktop-file-validate data/io.github.waylandifygui.WaylandifyGUI.desktop
```

测试使用临时目录，不会改动真实应用。覆盖系统文件不变、用户文件精确恢复、外部修改冲突、过期选择、嵌套 desktop ID、符号链接、参数插入与替换、刷新失败等行为。

核心逻辑测试使用临时目录，不改动真实应用配置。

Exec 编辑遵循 [freedesktop Desktop Entry 规范](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html) 的参数及字段占位符语义，不通过 shell 执行命令。

许可证：MIT。
