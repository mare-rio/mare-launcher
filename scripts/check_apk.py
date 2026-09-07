#!/usr/bin/env python3
"""Inspect the built production APK, including its binary manifest and provenance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def check(apk, sdk):
    meta = json.loads((ROOT / 'release.json').read_text())
    info = json.loads((apk.parent / 'release.json').read_text())
    assert info['apk'] == apk.name and not info['debuggable'], 'Production APK metadata required'
    assert hashlib.sha256(apk.read_bytes()).hexdigest() == info['apkSha256'], 'APK digest mismatch'
    tools = Path(sdk) / 'build-tools' / meta['buildTools']
    aapt = tools / ('aapt2.exe' if os.name == 'nt' else 'aapt2')
    badging = subprocess.run([str(aapt), 'dump', 'badging', str(apk)], check=True, capture_output=True, text=True).stdout
    assert "name='" + meta['package'] + "'" in badging
    assert "versionCode='" + str(meta['versionCode']) + "'" in badging
    assert "versionName='" + meta['version'] + "'" in badging
    assert "minSdkVersion:'" + str(meta['minSdk']) + "'" in badging
    assert "targetSdkVersion:'" + str(meta['targetSdk']) + "'" in badging
    assert 'application-debuggable' not in badging, 'Production manifest is debuggable'
    assert set(re.findall(r"uses-permission: name='([^']+)'", badging)) == {'android.permission.ACCESS_NETWORK_STATE'}
    manifest = subprocess.run([str(aapt), 'dump', 'xmltree', str(apk), '--file', 'AndroidManifest.xml'], check=True, capture_output=True, text=True).stdout
    for category in ['android.intent.category.HOME', 'android.intent.category.LEANBACK_LAUNCHER']:
        assert category in manifest
    with zipfile.ZipFile(apk) as bundle:
        names = set(bundle.namelist())
        assert 'classes.dex' in names
        for font in ['fraunces.ttf', 'fraunces-italic.ttf', 'inter.ttf', 'geist-mono.ttf']:
            assert 'assets/web/vendor/fonts/' + font in names
        for license_file in (ROOT / 'licenses').glob('*.txt'):
            assert 'assets/licenses/' + license_file.name in names
        assert 'assets/licenses/LICENSE-mare.txt' in names
        html = bundle.read('assets/web/index.html').decode()
        assert 'Content-Security-Policy' in html and "connect-src 'none'" in html
        assert not any(name.endswith(('.jks', '.keystore', '.p12')) for name in names)
        assert not any('node_modules/' in name or '.evidence/' in name for name in names)
    for name, digest in info['files'].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT), 'Unsafe provenance path'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Source changed since build: ' + name
    if info['signed']:
        signer = tools / ('apksigner.bat' if os.name == 'nt' else 'apksigner')
        result = subprocess.run([str(signer), 'verify', '--verbose', '--print-certs', str(apk)], check=True, capture_output=True, text=True).stdout
        assert 'certificate SHA-256 digest: ' + info['certificateSha256'] in result
    print('PASS: production manifest, permissions, packaged assets, licences, APK hash and source provenance' + ('; signature verified.' if info['signed'] else '; unsigned.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path)
    args = parser.parse_args()
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk:
        parser.error('Set ANDROID_HOME first.')
    info = json.loads((ROOT / 'dist/release.json').read_text())
    check(args.apk or ROOT / 'dist' / info['apk'], sdk)


if __name__ == '__main__':
    main()
