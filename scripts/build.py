#!/usr/bin/env python3
"""Build the same launcher for every TV using public, pinned dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ANDROID = '{http://schemas.android.com/apk/res/android}'


def run(args, **kwargs):
    result = subprocess.run([str(a) for a in args], text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true', help='Local development build with WebView inspection enabled')
    args = parser.parse_args()
    meta = json.loads((ROOT / 'release.json').read_text())
    sdk_value = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk_value:
        parser.error('Set ANDROID_HOME to your Android SDK directory. See docs/BUILDING.md.')
    sdk = Path(sdk_value)
    bt = sdk / 'build-tools' / meta['buildTools']
    jar = sdk / 'platforms' / ('android-' + str(meta['compileSdk'])) / 'android.jar'
    suffix = '.exe' if os.name == 'nt' else ''
    script_suffix = '.bat' if os.name == 'nt' else ''
    if not jar.is_file() or not bt.is_dir():
        parser.error('Install platforms;android-' + str(meta['compileSdk']) + ' and build-tools;' + meta['buildTools'])
    out = ROOT / '.build/android'
    if out.exists():
        shutil.rmtree(out)
    for directory in ['classes', 'dex', 'assets']:
        (out / directory).mkdir(parents=True, exist_ok=True)
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    run(['node', ROOT / 'scripts/build-web.cjs'], cwd=ROOT)
    shutil.copytree(ROOT / '.build/web', out / 'assets/web')
    shutil.copytree(ROOT / 'licenses', out / 'assets/licenses')
    shutil.copy2(ROOT / 'LICENSE', out / 'assets/licenses/LICENSE-mare.txt')
    manifest = ET.parse(ROOT / 'android/AndroidManifest.xml')
    manifest.getroot().set(ANDROID + 'versionCode', str(meta['versionCode']))
    manifest.getroot().set(ANDROID + 'versionName', meta['version'])
    manifest.getroot().find('uses-sdk').set(ANDROID + 'minSdkVersion', str(meta['minSdk']))
    manifest.getroot().find('uses-sdk').set(ANDROID + 'targetSdkVersion', str(meta['targetSdk']))
    manifest.getroot().find('application').set(ANDROID + 'debuggable', str(args.debug).lower())
    ET.register_namespace('android', ANDROID[1:-1])
    manifest.write(out / 'AndroidManifest.xml', encoding='utf-8', xml_declaration=True)
    run(['javac', '--release', '8', '-cp', jar, '-d', out / 'classes', *sorted((ROOT / 'android/src').glob('*.java'))])
    run([bt / ('d8' + script_suffix), '--min-api', meta['minSdk'], '--lib', jar,
         '--output', out / 'dex', *sorted((out / 'classes').rglob('*.class'))])
    run([bt / ('aapt2' + suffix), 'compile', '--dir', ROOT / 'android/res', '-o', out / 'resources.zip'])
    run([bt / ('aapt2' + suffix), 'link', '-I', jar, '--manifest', out / 'AndroidManifest.xml',
         '-R', out / 'resources.zip', '-A', out / 'assets', '-o', out / 'unsigned.apk'])
    with zipfile.ZipFile(out / 'unsigned.apk', 'a') as archive:
        archive.write(out / 'dex/classes.dex', 'classes.dex')
    run([bt / ('zipalign' + suffix), '-f', '4', out / 'unsigned.apk', out / 'aligned.apk'])
    key = None
    alias = 'mare-development'
    password_env = 'MARE_DEVELOPMENT_PASSWORD'
    env = os.environ.copy()
    if args.debug:
        key = ROOT / '.build/development.jks'
        alias = 'mare-development'
        env[password_env] = 'android'
        if not key.exists():
            run(['keytool', '-genkeypair', '-keystore', key, '-storepass:env', password_env,
                 '-keypass:env', password_env, '-alias', alias, '-dname', 'CN=Mare development',
                 '-keyalg', 'RSA', '-validity', '3650', '-noprompt'], env=env)
            key.chmod(0o600)
    apk = dist / ('mare-launcher-debug.apk' if args.debug else 'mare-launcher-unsigned.apk')
    certificate = None
    if key:
        if not env.get(password_env):
            parser.error('Set the password environment variable before signing; never put passwords in command arguments.')
        run([bt / ('apksigner' + script_suffix), 'sign', '--ks', key.resolve(), '--ks-key-alias', alias,
             '--ks-pass', 'env:' + password_env, '--key-pass', 'env:' + password_env,
             '--out', apk, out / 'aligned.apk'], env=env)
        output = run([bt / ('apksigner' + script_suffix), 'verify', '--verbose', '--print-certs', apk])
        certificate = next(line.split(': ', 1)[1] for line in output.splitlines() if 'certificate SHA-256 digest:' in line)
    else:
        shutil.copy2(out / 'aligned.apk', apk)
    tracked = [p for parent in ['android', 'web', 'vendor', 'scripts', 'licenses'] for p in (ROOT / parent).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts]
    tracked += [ROOT / name for name in ['LICENSE', 'release.json', 'package.json', 'package-lock.json', 'install.py']]
    provenance = {str(p.relative_to(ROOT)): sha(p) for p in sorted(tracked)}
    revision = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or None
    dirty = bool(subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain'], capture_output=True, text=True).stdout.strip()) if revision else True
    info = {**meta, 'apk': apk.name, 'apkSha256': sha(apk), 'apkBytes': apk.stat().st_size,
            'signed': bool(key), 'debuggable': args.debug, 'certificateSha256': certificate,
            'sourceRevision': revision, 'sourceDirty': dirty, 'files': provenance}
    (dist / 'release.json').write_text(json.dumps(info, indent=2) + '\n')
    (dist / 'SHA256SUMS').write_text(info['apkSha256'] + '  ' + apk.name + '\n')
    print(json.dumps({k: info[k] for k in ['version', 'apk', 'apkSha256', 'signed', 'debuggable']}, indent=2))


if __name__ == '__main__':
    main()
