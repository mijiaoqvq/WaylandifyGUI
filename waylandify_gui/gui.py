"""GTK4 frontend. All file and database operations run off the GTK thread."""
import threading
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk, Pango

from .core import EditError, Store, with_wayland


class Window(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title='WaylandifyGUI')
        self.set_default_size(1040, 720)
        self.set_size_request(760, 540)
        self.store = Store()
        self.selected = None
        self.busy = False
        self.apps = []
        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label='WaylandifyGUI', css_classes=['title']))
        self.refresh = Gtk.Button(icon_name='view-refresh-symbolic', tooltip_text='重新扫描应用')
        self.refresh.connect('clicked', lambda *_: self.scan())
        header.pack_end(self.refresh)
        self.set_titlebar(header)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)
        self.status = Gtk.Label(label='正在扫描应用…', xalign=0, wrap=True)
        self.status.set_margin_start(18)
        self.status.set_margin_end(18)
        self.status.set_margin_top(10)
        self.status.set_margin_bottom(10)
        root.append(self.status)
        pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        pane.set_vexpand(True)
        pane.set_position(340)
        root.append(pane)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ('start', 'end', 'top', 'bottom'):
            getattr(sidebar, f'set_margin_{side}')(12)
        self.search = Gtk.SearchEntry(placeholder_text='搜索应用名称、ID 或命令')
        self.search.connect('search-changed', lambda *_: self.filter_changed())
        sidebar.append(self.search)
        self.count = Gtk.Label(xalign=0, css_classes=['dim-label'])
        sidebar.append(self.count)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listbox.set_filter_func(self.matches)
        self.listbox.connect('row-selected', self.row_selected)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroll.set_child(self.listbox)
        sidebar.append(scroll)
        pane.set_start_child(sidebar)
        detail_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for side in ('start', 'end', 'top', 'bottom'):
            getattr(detail, f'set_margin_{side}')(24)
        detail_scroll.set_child(detail)
        pane.set_end_child(detail_scroll)
        self.title = Gtk.Label(label='选择一个应用', xalign=0, wrap=True, css_classes=['title-1'])
        detail.append(self.title)
        self.description = Gtk.Label(label='为 Electron / Chromium 应用添加 Wayland 启动参数。', xalign=0, wrap=True)
        detail.append(self.description)
        self.location = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=['dim-label'])
        self.location.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        detail.append(self.location)
        self.original = self.command_box(detail, '原始 Exec（修改前）')
        self.current_exec = self.command_box(detail, '当前 Exec')
        self.preview = self.command_box(detail, '应用后的 Exec')
        buttons = Gtk.Box(spacing=10)
        self.apply_button = Gtk.Button(label='启用 Wayland', css_classes=['suggested-action'])
        self.restore_button = Gtk.Button(label='恢复默认')
        self.apply_button.connect('clicked', lambda *_: self.change(False))
        self.restore_button.connect('clicked', lambda *_: self.change(True))
        buttons.append(self.apply_button)
        buttons.append(self.restore_button)
        detail.append(buttons)
        self.note = Gtk.Label(xalign=0, wrap=True, css_classes=['dim-label'])
        detail.append(self.note)
        explanation = Gtk.Label(label='此参数适用于支持 Ozone 的应用，不保证所有 Linux 程序都兼容。修改后请完全退出并重新打开目标应用。', xalign=0, wrap=True, css_classes=['dim-label'])
        detail.append(explanation)
        self.connect('close-request', self.close_requested)
        self.update_detail()
        self.scan()

    def close_requested(self, *_):
        if self.busy:
            self.status.set_text('正在处理文件，请等待操作完成后关闭。')
        return self.busy

    def command_box(self, parent, title):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(Gtk.Label(label=title, xalign=0, css_classes=['heading']))
        label = Gtk.Label(label='—', xalign=0, wrap=True, selectable=True, css_classes=['monospace'])
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        box.append(label)
        parent.append(box)
        return label

    def matches(self, row):
        query = self.search.get_text().casefold().strip()
        app = row.app
        return all(term in f'{app.name} {app.desktop_id} {app.command}'.casefold() for term in query.split())

    def filter_changed(self):
        self.listbox.invalidate_filter()
        visible = [row for row in self.rows if self.matches(row)] if hasattr(self, 'rows') else []
        self.count.set_text(f'{len(visible)} / {len(self.apps)} 个应用' if visible else '没有匹配的应用')
        row = self.listbox.get_selected_row()
        if row and not self.matches(row):
            self.listbox.unselect_all()

    def row_selected(self, _, row):
        self.selected = row.app if row else None
        self.update_detail()

    def update_detail(self):
        app = self.selected
        self.apply_button.set_sensitive(bool(app and not self.busy and not app.managed and not app.wayland and not app.reason))
        self.restore_button.set_sensitive(bool(app and app.managed and not app.conflict and not self.busy))
        if not app:
            self.title.set_text('选择一个应用')
            self.description.set_text('搜索并选择应用，查看启动命令和修改预览。')
            self.location.set_text('')
            for label in (self.original, self.current_exec, self.preview):
                label.set_text('—')
            self.note.set_text('')
            return
        self.title.set_text(app.name)
        self.description.set_text('外部修改冲突' if app.conflict else '已由 WaylandifyGUI 管理' if app.managed else '已包含 Wayland 参数' if app.wayland else '尚未启用 Wayland 参数')
        self.location.set_text(f'{app.desktop_id}\n{app.path}')
        self.original.set_text(app.original_command)
        self.current_exec.set_text(app.command)
        try:
            self.preview.set_text(with_wayland(app.command))
        except EditError:
            self.preview.set_text('无法自动生成')
        if app.conflict:
            note = '文件已被其他程序修改，自动恢复已禁用。原始备份保留在 ' + str(self.store.state)
        elif app.managed:
            note = '恢复会还原原有用户文件；若原本没有用户文件，则删除覆盖，让系统默认配置重新生效。'
        elif app.wayland:
            note = '参数已存在；缺少 WaylandifyGUI 原始备份，因此不会自动删除。'
        elif app.reason:
            note = app.reason
        else:
            target = app.path if app.path.is_relative_to(self.store.user) else self.store.user / app.desktop_id
            note = f'将写入：{target}\n仅修改主启动命令，保留桌面快捷操作。若启用了 D-Bus 激活，将关闭它以确保 Exec 生效。'
        self.note.set_text(note)

    def run_background(self, operation, completed):
        if self.busy:
            return
        self.busy = True
        self.refresh.set_sensitive(False)
        self.update_detail()

        def worker():
            try:
                result = operation()
                error = None
            except Exception as exc:
                result, error = None, str(exc)
            GLib.idle_add(deliver, result, error)

        def deliver(result, error):
            self.busy = False
            self.refresh.set_sensitive(True)
            completed(result, error)
            self.update_detail()
            return GLib.SOURCE_REMOVE

        threading.Thread(target=worker, daemon=False).start()

    def scan(self, message=None, keep_id=None):
        if self.busy:
            return
        keep_id = keep_id or (self.selected.desktop_id if self.selected else None)
        self.status.set_text('正在扫描应用…')

        def complete(apps, error):
            if error:
                self.status.set_text('扫描失败：' + error)
                return
            self.apps = apps
            while (child := self.listbox.get_first_child()) is not None:
                self.listbox.remove(child)
            self.rows = []
            selected_row = None
            for app in apps:
                row = Gtk.ListBoxRow()
                row.app = app
                box = Gtk.Box(spacing=12)
                for side in ('start', 'end', 'top', 'bottom'):
                    getattr(box, f'set_margin_{side}')(10)
                icon = Gtk.Image(pixel_size=32)
                if app.icon.startswith('/') and Path(app.icon).is_file():
                    icon.set_from_file(app.icon)
                else:
                    icon.set_from_icon_name(app.icon or 'application-x-executable')
                box.append(icon)
                info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
                name = Gtk.Label(label=app.name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
                name.set_max_width_chars(32)
                info.append(name)
                state = '冲突 · 备份已保留' if app.conflict else 'Wayland · 可恢复' if app.managed else 'Wayland · 已存在' if app.wayland else '用户应用' if app.path.is_relative_to(self.store.user) else '系统应用'
                info.append(Gtk.Label(label=state, xalign=0, css_classes=['dim-label']))
                box.append(info)
                row.set_child(box)
                row.set_tooltip_text(app.desktop_id)
                self.rows.append(row)
                self.listbox.append(row)
                if app.desktop_id == keep_id:
                    selected_row = row
            if selected_row and self.matches(selected_row):
                self.listbox.select_row(selected_row)
            self.filter_changed()
            status = message or f'扫描完成 · {len(apps)} 个应用'
            if self.store.warnings:
                status += f' · {len(self.store.warnings)} 条扫描提示（悬停查看）'
            self.status.set_text(status)
            self.status.set_tooltip_text('\n'.join(self.store.warnings) or None)

        self.run_background(self.store.scan, complete)

    def change(self, restore):
        app = self.selected
        if not app or self.busy:
            return
        self.status.set_text('正在恢复并刷新桌面数据库…' if restore else '正在创建用户覆盖并刷新桌面数据库…')

        def complete(message, error):
            self.scan(('操作失败：' + error) if error else ('已恢复。' if restore else '已启用 Wayland。') + message, app.desktop_id)

        self.run_background(lambda: self.store.restore(app) if restore else self.store.apply(app), complete)


class WaylandifyGUI(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.waylandifygui.WaylandifyGUI', flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        window = self.get_active_window()
        if window is None:
            window = Window(self)
        window.present()


def main():
    return WaylandifyGUI().run(None)
