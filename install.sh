#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
prefix=${PREFIX:-"$HOME/.local"}
case "$prefix" in /*) ;; *) echo 'PREFIX 必须是绝对路径' >&2; exit 1;; esac
mkdir -p "$prefix/lib/waylandify-gui" "$prefix/bin" "$prefix/share/applications" "$prefix/share/icons/hicolor/scalable/apps"
cp -R "$root/waylandify_gui" "$prefix/lib/waylandify-gui/"
cp "$root/waylandify-gui" "$prefix/lib/waylandify-gui/waylandify-gui"
ln -sfn "$prefix/lib/waylandify-gui/waylandify-gui" "$prefix/bin/waylandify-gui"
# Encode a desktop Exec path without using shell quoting rules.
python3 - "$root" "$prefix" <<'PY'
from pathlib import Path
import sys
root, prefix = map(Path, sys.argv[1:])
path = str(prefix / 'bin/waylandify-gui')
for char, replacement in [('\\', '\\\\\\\\'), ('"', '\\\\"'), ('`', '\\\\`'), ('$', '\\\\$'), ('%', '%%')]:
    path = path.replace(char, replacement)
text = (root / 'data/io.github.waylandifygui.WaylandifyGUI.desktop').read_text()
text = text.replace('Exec=waylandify-gui', f'Exec="{path}"')
(prefix / 'share/applications/io.github.waylandifygui.WaylandifyGUI.desktop').write_text(text)
PY
cp "$root/data/io.github.waylandifygui.WaylandifyGUI.svg" "$prefix/share/icons/hicolor/scalable/apps/"
update-desktop-database "$prefix/share/applications"
printf '已安装到 %s\n' "$prefix"
