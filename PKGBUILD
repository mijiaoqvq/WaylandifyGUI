# Local build. For AUR publication, use tools/prepare-aur.py after hosting the release.
pkgname=waylandify-gui
pkgver=1.1.0
pkgrel=1
pkgdesc='GTK4 GUI for managing user-level Wayland desktop launch overrides'
arch=('any')
license=('MIT')
depends=('python' 'python-gobject' 'gtk4' 'desktop-file-utils')
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('5252dd90d0e9286b0d2f1f78252e1c1c4c50cfcb72952357567b694bc21fbb85')

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
