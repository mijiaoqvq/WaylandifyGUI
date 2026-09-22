#!/usr/bin/env python3
"""Create the release source archive and refresh local Arch metadata."""
import gzip
import hashlib
from pathlib import Path
import re
import subprocess
import tarfile

root = Path(__file__).resolve().parents[1]
version = re.search(r'__version__ = [\'"]([^\'"]+)', (root / 'waylandify_gui/__init__.py').read_text())[1]
name = f'waylandify-gui-{version}'
archive = root / f'{name}.tar.gz'
paths = [root / x for x in ('LICENSE', 'README.md', 'PACKAGING.md', 'install.sh', 'waylandify-gui')]
for directory in ('waylandify_gui', 'tests', 'data'):
    paths.extend(p for p in (root / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
with archive.open('wb') as stream, gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as tar:
    for path in sorted(paths):
        info = tar.gettarinfo(str(path), f'{name}/{path.relative_to(root)}')
        info.uid = info.gid = info.mtime = 0
        info.uname = info.gname = ''
        with path.open('rb') as source:
            tar.addfile(info, source)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
build = root / 'PKGBUILD'
text = build.read_text()
text = re.sub(r'^pkgver=.*$', 'pkgver=' + version, text, flags=re.M)
text = re.sub(r'^sha256sums=.*$', f"sha256sums=('{checksum}')", text, flags=re.M)
build.write_text(text)
result = subprocess.run(['makepkg', '--printsrcinfo'], cwd=root, check=True, capture_output=True, text=True)
(root / '.SRCINFO').write_text(result.stdout)
print(f'{archive.name}: {checksum}')
