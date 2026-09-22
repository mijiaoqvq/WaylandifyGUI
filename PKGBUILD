# Local build. For AUR publication, use tools/prepare-aur.py after hosting the release.
pkgname=waylandify-gui
pkgver=1.1.0
pkgrel=1
pkgdesc='GTK4 GUI for managing user-level Wayland desktop launch overrides'
arch=('any')
license=('MIT')
depends=('python' 'python-gobject' 'gtk4' 'desktop-file-utils')
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('708aa73740f800e7b00a32d9fb4c3a164a9667c4e915bc14643f40b905d3da7d')

check() {
  cd "$srcdir/$pkgname-$pkgver"
  python -m unittest discover -s tests -v
  desktop-file-validate data/io.github.waylandifygui.WaylandifyGUI.desktop
}

package() {
  cd "$srcdir/$pkgname-$pkgver"
  install -dm755 "$pkgdir/usr/lib/$pkgname/waylandify_gui" "$pkgdir/usr/bin"
  install -m644 waylandify_gui/*.py "$pkgdir/usr/lib/$pkgname/waylandify_gui/"
  install -m755 waylandify-gui "$pkgdir/usr/lib/$pkgname/waylandify-gui"
  ln -s "/usr/lib/$pkgname/waylandify-gui" "$pkgdir/usr/bin/waylandify-gui"
  install -Dm644 data/io.github.waylandifygui.WaylandifyGUI.desktop "$pkgdir/usr/share/applications/io.github.waylandifygui.WaylandifyGUI.desktop"
  install -Dm644 data/io.github.waylandifygui.WaylandifyGUI.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/io.github.waylandifygui.WaylandifyGUI.svg"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}
