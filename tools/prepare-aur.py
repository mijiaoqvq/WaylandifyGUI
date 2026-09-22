#!/usr/bin/env python3
"""Generate AUR metadata from a published GitHub version tag."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', default='https://github.com/mijiaoqvq/WaylandifyGUI')
args = parser.parse_args()
repo = args.repo.rstrip('/')
if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
    parser.error('需要真实的 GitHub 仓库 URL：https://github.com/OWNER/REPO')
root = Path(__file__).resolve().parents[1]
version = re.search(r'__version__ = [\'"]([^\'"]+)', (root / 'waylandify_gui/__init__.py').read_text())[1]
url = f'{repo}/archive/refs/tags/v{version}.tar.gz'
with urllib.request.urlopen(url, timeout=60) as response:
    checksum = hashlib.sha256(response.read()).hexdigest()
text = (root / 'PKGBUILD').read_text()
text = text.replace('# Local build. For AUR publication, use tools/prepare-aur.py after hosting the release.\n', '')
text = text.replace("arch=('any')", f'url=\'{repo}\'\narch=(\'any\')')
text = text.replace('source=("$pkgname-$pkgver.tar.gz")', 'source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")')
text = text.replace('$srcdir/$pkgname-$pkgver', f'$srcdir/{repo.rsplit("/", 1)[1]}-$pkgver')
text = re.sub(r'^sha256sums=.*$', f"sha256sums=('{checksum}')", text, flags=re.M)
destination = root / 'aur'
destination.mkdir(exist_ok=True)
(destination / 'PKGBUILD').write_text(text)
result = subprocess.run(['makepkg', '--printsrcinfo'], cwd=destination, check=True, text=True, capture_output=True)
(destination / '.SRCINFO').write_text(result.stdout)
print(f'已生成：{destination}\n源码：{url}\nSHA256：{checksum}')
print('仅生成配方；没有推送 AUR。')
