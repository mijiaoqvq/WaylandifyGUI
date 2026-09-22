import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from waylandify_gui.core import EditError, Store, has_wayland, values, with_wayland

DESKTOP = b'''[Desktop Entry]\nType=Application\nName=Example\nName[zh_CN]=Example Chinese\nIcon=example\nExec=/opt/example/app %U\nDBusActivatable=true\nActions=New;\n\n[Desktop Action New]\nName=New window\nExec=/opt/example/app --new-window\n'''


class CommandTests(unittest.TestCase):
    def test_insert_and_preserve(self):
        command = '"/opt/My App/app" --name="a b" %U'
        self.assertEqual(with_wayland(command), '"/opt/My App/app" --ozone-platform=wayland --name="a b" %U')

    def test_environment(self):
        self.assertEqual(with_wayland('env FOO=bar "HELLO=a b" /bin/app %F'), 'env FOO=bar "HELLO=a b" /bin/app --ozone-platform=wayland %F')

    def test_replace(self):
        for command in ('app --ozone-platform=x11 %U', 'app --ozone-platform x11 %U'):
            self.assertEqual(with_wayland(command), 'app --ozone-platform=wayland %U')

    def test_idempotent(self):
        command = 'app --ozone-platform=wayland %U'
        self.assertEqual(with_wayland(command), command)
        self.assertTrue(has_wayland('app --ozone-platform wayland %U'))
        self.assertFalse(has_wayland('app -- --ozone-platform=wayland'))

    def test_separator(self):
        self.assertEqual(with_wayland('app -- %F'), 'app --ozone-platform=wayland -- %F')

    def test_reject_unsafe(self):
        for command in ('sh -c "app %U"', 'env -u FOO app', 'flatpak run org.app.App', 'app "unterminated', 'app --ozone-platform', 'app --ozone-platform=x11 --ozone-platform=auto'):
            with self.subTest(command=command), self.assertRaises(EditError):
                with_wayland(command)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'system', self.root / 'user', self.root / 'state')
        self.store.system.mkdir()
        self.source = self.store.system / 'app.desktop'
        self.source.write_bytes(DESKTOP)
        self.refresh = patch.object(self.store, 'refresh_database', return_value='OK')
        self.refresh.start()

    def tearDown(self):
        self.refresh.stop()
        self.temp.cleanup()

    def app(self):
        return self.store.scan()[0]

    def test_system_overlay_and_restore(self):
        app = self.app()
        self.store.apply(app)
        updated = self.app()
        self.assertTrue(updated.managed)
        self.assertTrue(updated.wayland)
        self.assertEqual(updated.original_command, '/opt/example/app %U')
        self.assertEqual(self.source.read_bytes(), DESKTOP)
        self.assertIn(b'Exec=/opt/example/app --new-window', updated.data)
        self.assertEqual(values(updated.data.decode())['DBusActivatable'], 'false')
        self.store.restore(updated)
        self.assertFalse((self.store.user / 'app.desktop').exists())
        self.assertFalse(self.app().managed)
        self.assertEqual(self.source.read_bytes(), DESKTOP)
        self.assertEqual(self.store.refresh_database.call_count, 2)

    def test_user_backup_exact_restore(self):
        self.store.user.mkdir()
        target = self.store.user / 'app.desktop'
        original = DESKTOP.replace(b'Name=Example', b'Name=Custom').replace(b'\n', b'\r\n')
        target.write_bytes(original)
        target.chmod(0o640)
        self.store.apply(self.app())
        self.store.restore(self.app())
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)

    def test_user_only(self):
        self.source.unlink()
        self.store.user.mkdir()
        (self.store.user / 'app.desktop').write_bytes(DESKTOP)
        self.store.apply(self.app())
        self.store.restore(self.app())
        self.assertEqual(self.app().data, DESKTOP)

    def test_external_edit_conflict(self):
        self.store.apply(self.app())
        target = self.app().path
        target.write_bytes(target.read_bytes() + b'# external change\n')
        changed = target.read_bytes()
        self.assertTrue(self.app().conflict)
        with self.assertRaises(EditError):
            self.store.restore(self.app())
        self.assertEqual(target.read_bytes(), changed)
        self.assertTrue(self.store.record_path('app.desktop').exists())

    def test_stale_selection(self):
        app = self.app()
        self.source.write_bytes(DESKTOP + b'# update\n')
        with self.assertRaises(EditError):
            self.store.apply(app)

    def test_existing_external_flag(self):
        self.source.write_bytes(DESKTOP.replace(b'app %U', b'app --ozone-platform=wayland %U'))
        self.assertTrue(self.app().wayland)
        with self.assertRaises(EditError):
            self.store.apply(self.app())
        with self.assertRaises(EditError):
            self.store.restore(self.app())

    def test_hidden_override_masks_system(self):
        self.store.user.mkdir()
        (self.store.user / 'app.desktop').write_bytes(DESKTOP + b'\n[Desktop Entry]\nType=Application\nHidden=true\nExec=app\n')
        self.assertEqual(self.store.scan(), [])

    def test_nested_id(self):
        nested = self.store.system / 'vendor'
        nested.mkdir()
        self.source.rename(nested / 'app.desktop')
        self.assertEqual(self.app().desktop_id, 'vendor-app.desktop')
        self.store.apply(self.app())
        self.assertEqual(self.app().path, self.store.user / 'vendor-app.desktop')
        self.store.restore(self.app())

    def test_symlink_user_rejected(self):
        self.store.user.mkdir()
        (self.store.user / 'app.desktop').symlink_to(self.source)
        with self.assertRaises(EditError):
            self.store.apply(self.app())
        self.assertEqual(self.source.read_bytes(), DESKTOP)

    def test_write_failure_keeps_original(self):
        import waylandify_gui.core as core
        real = core.atomic_write
        def fail_target(path, data, mode=0o644):
            if path.suffix == '.desktop':
                raise OSError('disk full')
            return real(path, data, mode)
        with patch('waylandify_gui.core.atomic_write', side_effect=fail_target), self.assertRaises(OSError):
            self.store.apply(self.app())
        self.assertFalse(self.store.record_path('app.desktop').exists())
        self.assertEqual(self.source.read_bytes(), DESKTOP)

    def test_database_argument_and_failure(self):
        self.refresh.stop()
        with patch('waylandify_gui.core.shutil.which', return_value='/usr/bin/update-desktop-database'), patch('waylandify_gui.core.subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'failure')) as run:
            result = self.store.refresh_database()
            self.assertIn('刷新失败', result)
            self.assertEqual(run.call_args.args[0], ['/usr/bin/update-desktop-database', str(self.store.user)])
        self.refresh.start()

    def test_locale(self):
        with patch.dict(os.environ, {'LC_ALL': 'zh_CN.UTF-8'}):
            self.assertEqual(self.app().name, 'Example Chinese')


if __name__ == '__main__':
    unittest.main()
