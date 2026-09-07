#!/usr/bin/env python3
"""Prepare a local installation ZIP. Never uploads or publishes anything."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def create_bundle(root, apk, output):
    info = json.loads((apk.parent / 'release.json').read_text())
    if (not info.get('signed') or info.get('debuggable') or info.get('apk') != apk.name
            or info.get('package') != 'rio.dan.mare.launcher'):
        raise ValueError('Only a signed production APK can become an installation bundle.')
    if not re.fullmatch(r'\d+\.\d+\.\d+', info['version']):
        raise ValueError('Invalid version.')
    if not info.get('sourceRevision') or info.get('sourceDirty'):
        raise ValueError('Build from a committed, clean source tree before packaging.')
    if hashlib.sha256(apk.read_bytes()).hexdigest() != info['apkSha256']:
        raise ValueError('APK checksum does not match release.json.')
    # An explicit allowlist keeps keys, device captures and development files out.
    names = ['install.py', 'install.cmd', 'install.command', 'install.sh', 'README.md', 'LICENSE',
             'THIRD_PARTY_NOTICES.md', 'SECURITY.md', 'CONTRIBUTING.md', 'scripts/platform-tools.json',
             'docs/INSTALLATION.md', 'docs/COMPATIBILITY.md', 'docs/CI_SECURITY.md',
             'docs/BUILDING.md', 'docs/images/home-night.png', 'docs/images/home-day.png']
    names += [str(p.relative_to(root)).replace('\\', '/') for p in sorted((root / 'licenses').glob('*.txt'))]
    files = {name: root / name for name in names}
    files.update({'mare-launcher.apk': apk, 'release.json': apk.parent / 'release.json'})
    if any(not path.is_file() or path.is_symlink() for path in files.values()):
        raise ValueError('Bundle input is missing or is a symbolic link.')
    output.parent.mkdir(parents=True, exist_ok=True)
    checksum = ''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + name + '\n' for name, path in sorted(files.items()))
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, path in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (0o100755 if name in ['install.py', 'install.sh', 'install.command'] else 0o100644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(entry, path.read_bytes())
        bundle.writestr('SHA256SUMS', checksum)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, default=ROOT / 'dist/mare-launcher.apk')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    info = json.loads((args.apk.parent / 'release.json').read_text())
    output = args.output or ROOT / 'dist' / ('mare-launcher-' + info['version'] + '-install.zip')
    digest = create_bundle(ROOT, args.apk, output)
    print('Prepared locally: ' + str(output) + '\nSHA256: ' + digest + '\nNothing was published.')


if __name__ == '__main__':
    main()
