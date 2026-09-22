# Arch Linux 与 AUR 打包

应用名：**WaylandifyGUI**；Arch 包名和命令：`waylandify-gui`；版本：1.1.0。

## 本地系统安装

在源码目录中执行（不要以 root 运行 makepkg）：

```sh
sudo pacman -S --needed base-devel python
python tools/make-release.py
makepkg -si
```

PKGBUILD 从旁边的 `waylandify-gui-1.1.0.tar.gz` 获取源码，校验 SHA-256，在 `$srcdir` 运行测试并在 `$pkgdir` 安装。无需从构建目录之外复制文件。生成的包可用 `sudo pacman -U ./waylandify-gui-1.1.0-1-any.pkg.tar.zst` 安装，随后运行 `waylandify-gui`。

文件布局：

- `/usr/bin/waylandify-gui`：启动命令
- `/usr/lib/waylandify-gui/`：程序与私有 Python 模块
- `/usr/share/applications/io.github.waylandifygui.WaylandifyGUI.desktop`：应用菜单入口
- `/usr/share/icons/hicolor/scalable/apps/io.github.waylandifygui.WaylandifyGUI.svg`：图标
- `/usr/share/licenses/waylandify-gui/LICENSE`：许可证
- `/usr/share/doc/waylandify-gui/README.md`：说明

依赖 `python`、`python-gobject`、`gtk4`、`desktop-file-utils`。使用系统现有 desktop/icon pacman hooks，无需在包安装脚本中重复刷新。安装包本身不修改任何用户应用覆盖。

卸载程序用 `sudo pacman -Rns waylandify-gui`。卸载不会删除用户覆盖或恢复记录；若希望恢复应用默认启动方式，请在卸载前在界面中恢复。

## 正式发布 AUR

AUR 托管构建配方，正式发布还需要本项目自己的公开源码仓库和可下载的源码归档。不要把另一个 Waylandify 项目当作本项目的上游地址。

1. 项目源码仓库为 https://github.com/mijiaoqvq/WaylandifyGUI 。提交源码后创建并推送 `v1.1.0` 标签；源码使用 GitHub 的固定标签归档，无需单独上传 Release asset。
2. 生成 AUR 配方：

   ```sh
   python tools/prepare-aur.py
   ```

   脚本下载标签源码，计算 SHA-256，生成 `aur/PKGBUILD` 和 `aur/.SRCINFO`。源码解压目录与 GitHub 仓库名一致。脚本不推送 AUR。
3. 在一个不含本地源码归档的干净目录中复制这两个文件，用 `makepkg -s` 验证下载与构建；可使用 Arch `devtools` 在干净 chroot 中进一步验证。
4. 注册 AUR 账号并配置 SSH 公钥，重新确认 `waylandify-gui` 名称可用，再推送：

   ```sh
   git clone ssh://aur@aur.archlinux.org/waylandify-gui.git aur-submit
   cp aur/PKGBUILD aur/.SRCINFO aur-submit/
   cd aur-submit
   git add PKGBUILD .SRCINFO
   git commit -m 'Initial release: 1.1.0'
   git push
   ```

发布成功后才可使用 `yay -S waylandify-gui`。目前交付中的本地 PKGBUILD 不是已发布的 AUR 包，也不能把本地 `source` 配方直接提交。

后续改动源码时更新版本，提交源码并推送新标签，重新生成 AUR 配方、校验和及 `.SRCINFO`。已发布的标签不要移动。仅调整打包逻辑时更新 `pkgrel`。

参考：[PKGBUILD 官方手册](https://man.archlinux.org/man/PKGBUILD.5.en)。
