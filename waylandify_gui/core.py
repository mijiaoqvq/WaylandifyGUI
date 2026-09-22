"""Desktop entry editing without executing Exec or touching system files."""
from __future__ import annotations

import base64
import contextlib
from dataclasses import dataclass
import fcntl
import hashlib
import json
import locale
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

FLAG = '--ozone-platform=wayland'


class EditError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def values(text: str) -> dict[str, str]:
    result = {}
    active = False
    for line in text.splitlines():
        if line.startswith('['):
            active = line.strip() == '[Desktop Entry]'
        elif active and '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def replace_key(text: str, key: str, value: str) -> str:
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.strip() == '[Desktop Entry]'), None)
    if start is None:
        raise EditError('缺少 [Desktop Entry]。')
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('[')), len(lines))
    newline = '\r\n' if '\r\n' in text else '\n'
    found = [i for i in range(start + 1, end) if lines[i].split('=', 1)[0].strip() == key and '=' in lines[i]]
    if len(found) > 1:
        raise EditError(f'存在重复的 {key}，无法安全修改。')
    if found:
        lines[found[0]] = f'{key}={value}{newline}'
    else:
        if end and not lines[end - 1].endswith('\n'):
            lines[end - 1] += newline
        lines.insert(end, f'{key}={value}{newline}')
    return ''.join(lines)


# Token spans preserve the original quoting and all desktop field codes.
TOKEN = re.compile(r'(?:"(?:\\.|[^"\\])*"|\\.|[^\s"\\])+')


def tokens(command: str):
    matches = list(TOKEN.finditer(command))
    cursor = 0
    result = []
    for match in matches:
        if command[cursor:match.start()].strip():
            raise EditError('Exec 引号或转义无效。')
        raw = match.group()
        try:
            parsed = shlex.split(raw, posix=True)
        except ValueError as exc:
            raise EditError('Exec 引号或转义无效。') from exc
        if len(parsed) != 1:
            raise EditError('Exec 格式不受支持。')
        result.append((parsed[0], match.start(), match.end()))
        cursor = match.end()
    if command[cursor:].strip() or not result:
        raise EditError('Exec 为空或格式无效。')
    return result


def executable_index(parts):
    index = 0
    if Path(parts[0][0]).name == 'env':
        index = 1
        while index < len(parts) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', parts[index][0], re.S):
            index += 1
        if index == len(parts) or parts[index][0].startswith('-'):
            raise EditError('暂不支持带选项的 env 命令。')
    executable = Path(parts[index][0]).name
    if executable in {'sh', 'bash', 'zsh', 'fish', 'dash', 'flatpak', 'snap', 'gtk-launch', 'gio', 'python', 'python3', 'perl', 'ruby', 'node', 'wine', 'wine64', 'sudo', 'pkexec'}:
        raise EditError('这是脚本、容器或间接启动命令，无法可靠确定参数位置。')
    return index


def with_wayland(command: str) -> str:
    parts = tokens(command)
    index = executable_index(parts)
    # Ignore anything after --: those are positional arguments, not switches.
    end = next((i for i in range(index + 1, len(parts)) if parts[i][0] == '--'), len(parts))
    ozone = [i for i in range(index + 1, end) if parts[i][0] == '--ozone-platform' or parts[i][0].startswith('--ozone-platform=')]
    if len(ozone) > 1:
        raise EditError('Exec 包含多个 ozone-platform 参数，请先手动整理。')
    if ozone:
        i = ozone[0]
        stop = parts[i][2]
        if parts[i][0] == '--ozone-platform':
            if i + 1 >= end or parts[i + 1][0].startswith(('-', '%')):
                raise EditError('ozone-platform 缺少参数值。')
            stop = parts[i + 1][2]
        return command[:parts[i][1]] + FLAG + command[stop:]
    position = parts[index][2]
    return command[:position] + ' ' + FLAG + command[position:]


def has_wayland(command: str) -> bool:
    try:
        parts = tokens(command)
        index = executable_index(parts)
        args = [p[0] for p in parts[index + 1:]]
        args = args[:args.index('--')] if '--' in args else args
        return FLAG in args or any(a == '--ozone-platform' and b == 'wayland' for a, b in zip(args, args[1:]))
    except EditError:
        return False


def localized_name(fields):
    lang = (os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG') or locale.getlocale()[0] or '').split('.')[0]
    base, _, modifier = lang.partition('@')
    candidates = [lang, base]
    if '_' in base:
        language = base.split('_')[0]
        if modifier:
            candidates.append(language + '@' + modifier)
        candidates.append(language)
    name = next((fields[f'Name[{candidate}]'] for candidate in candidates if f'Name[{candidate}]' in fields), fields.get('Name', ''))
    return re.sub(r'\\([sntr\\])', lambda m: {'s': ' ', 'n': '\n', 't': '\t', 'r': '\r', '\\': '\\'}[m[1]], name)


def atomic_write(path: Path, data: bytes, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.waylandify-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass
class Application:
    desktop_id: str
    path: Path
    system_path: Path | None
    data: bytes
    name: str
    icon: str
    command: str
    managed: bool
    wayland: bool
    conflict: bool
    reason: str
    record: dict | None = None

    @property
    def original_command(self):
        if self.record:
            return values(base64.b64decode(self.record['source']).decode('utf-8')).get('Exec', '')
        return self.command


class Store:
    def __init__(self, system=None, user=None, state=None):
        self.system = Path(system or '/usr/share/applications')
        self.user = Path(user or Path.home() / '.local/share/applications')
        # Keep the 1.0 backup directory so a rename cannot strand existing overrides.
        self.state = Path(state or Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'waylandify')
        self.warnings = []

    def record_path(self, desktop_id):
        return self.state / (digest(desktop_id.encode()) + '.json')

    def record(self, desktop_id):
        path = self.record_path(desktop_id)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text())
            if record['id'] != desktop_id or record['version'] != 1:
                raise ValueError('记录版本或 ID 不匹配')
            for key in ('source', 'after', 'before', 'target', 'mode'):
                record[key]
            base64.b64decode(record['source'], validate=True)
            if record['before'] is not None:
                base64.b64decode(record['before'], validate=True)
            return record
        except (ValueError, KeyError, TypeError) as exc:
            raise EditError(f'备份记录损坏：{path.name}') from exc

    def inventory(self, root):
        entries = {}
        if root.exists():
            for path in sorted(root.rglob('*.desktop')):
                desktop_id = str(path.relative_to(root)).replace('/', '-')
                if desktop_id in entries:
                    self.warnings.append(f'重复 desktop ID：{desktop_id}，已跳过。')
                    entries[desktop_id] = None
                else:
                    entries[desktop_id] = path
        return entries

    def scan(self):
        self.warnings = []
        system, user = self.inventory(self.system), self.inventory(self.user)
        apps = []
        for desktop_id in system.keys() | user.keys():
            path = user.get(desktop_id) if desktop_id in user else system[desktop_id]
            if path is None:
                continue
            try:
                data = path.read_bytes()
                fields = values(data.decode('utf-8'))
                record = self.record(desktop_id)
                if fields.get('Type') != 'Application' or not fields.get('Exec'):
                    continue
                if fields.get('Hidden', '').lower() == 'true' and not record:
                    continue
                command = fields['Exec']
                reason = ''
                try:
                    with_wayland(command)
                except EditError as exc:
                    reason = str(exc)
                managed = bool(record)
                conflict = bool(record and (digest(data) != record['after'] or str(path) != record['target']))
                if path.is_symlink():
                    reason = '用户级符号链接不支持自动覆盖。' if desktop_id in user else reason
                apps.append(Application(desktop_id, path, system.get(desktop_id), data, localized_name(fields) or desktop_id, fields.get('Icon', ''), command, managed, has_wayland(command), conflict, reason, record))
            except (OSError, UnicodeError, EditError) as exc:
                self.warnings.append(f'{desktop_id}：{exc}')
        return sorted(apps, key=lambda app: (app.name.casefold(), app.desktop_id))

    @contextlib.contextmanager
    def locked(self):
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.state / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def current(self, app):
        fresh = next((a for a in self.scan() if a.desktop_id == app.desktop_id), None)
        if fresh is None or fresh.data != app.data or fresh.path != app.path:
            raise EditError('应用文件已变化，请刷新后重试。')
        return fresh

    def refresh_database(self):
        executable = shutil.which('update-desktop-database')
        if not executable:
            return '文件已更新，但未找到 update-desktop-database；请安装 desktop-file-utils 后刷新。'
        try:
            result = subprocess.run([executable, str(self.user)], capture_output=True, text=True, timeout=20)
            if result.returncode:
                return '文件已更新，但桌面数据库刷新失败：' + (result.stderr.strip() or str(result.returncode))
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f'文件已更新，但桌面数据库刷新失败：{exc}'
        return '已刷新桌面数据库。重新启动目标应用后生效。'

    def apply(self, app):
        with self.locked():
            app = self.current(app)
            if app.managed or app.wayland:
                raise EditError('该应用已添加参数或已有备份记录。')
            if app.reason:
                raise EditError(app.reason)
            target = app.path if app.path.is_relative_to(self.user) else self.user / app.desktop_id
            if target.is_symlink() or not target.parent.resolve().is_relative_to(self.user.resolve()):
                raise EditError('覆盖目标不可为符号链接或位于应用目录之外。')
            before = target.read_bytes() if target.exists() else None
            mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
            text = replace_key(app.data.decode('utf-8'), 'Exec', with_wayland(app.command))
            # D-Bus activation can bypass Exec entirely.
            if values(text).get('DBusActivatable', '').lower() == 'true':
                text = replace_key(text, 'DBusActivatable', 'false')
            after = text.encode('utf-8')
            record = dict(version=1, id=app.desktop_id, target=str(target), mode=mode,
                          source=base64.b64encode(app.data).decode(),
                          before=base64.b64encode(before).decode() if before is not None else None,
                          after=digest(after))
            record_path = self.record_path(app.desktop_id)
            atomic_write(record_path, json.dumps(record, ensure_ascii=False, indent=2).encode(), 0o600)
            try:
                atomic_write(target, after, mode)
            except OSError:
                record_path.unlink()
                raise
        return self.refresh_database()

    def restore(self, app):
        with self.locked():
            app = self.current(app)
            record = app.record
            if not record:
                raise EditError('此参数不是由 WaylandifyGUI 添加，缺少原始备份，不能安全恢复。')
            target = Path(record['target'])
            if app.conflict or target.is_symlink() or not target.is_relative_to(self.user) or not target.parent.resolve().is_relative_to(self.user.resolve()):
                raise EditError('覆盖文件已被外部修改或移动；为保护现有内容，已停止恢复。备份仍然保留。')
            if record['before'] is None:
                target.unlink()
            else:
                atomic_write(target, base64.b64decode(record['before']), record['mode'])
            self.record_path(app.desktop_id).unlink()
        return self.refresh_database()
