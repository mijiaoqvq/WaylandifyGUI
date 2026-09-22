import sys

try:
    from .gui import main
except (ImportError, ValueError, AttributeError) as exc:
    print('WaylandifyGUI 需要 GTK4 与 PyGObject。Arch Linux：sudo pacman -S gtk4 python-gobject desktop-file-utils', file=sys.stderr)
    print(f'依赖加载失败：{exc}', file=sys.stderr)
    raise SystemExit(1)

raise SystemExit(main())
