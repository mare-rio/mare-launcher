#!/usr/bin/env python3
"""Sign an already reviewed APK locally. This helper never executes build code."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--keystore', required=True, type=Path)
    parser.add_argument('--key-alias', default='mare-launcher')
    parser.add_argument('--password-env', default='MARE_KEYSTORE_PASSWORD')
    parser.add_argument('--build-tools', default='36.0.0', help='Trusted local SDK tool version; never taken from artifact metadata')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.build_tools):
        parser.error('Invalid Android build-tools version.')
    apk = args.apk.resolve()
    metadata = apk.parent / 'release.json'
    info = json.loads(metadata.read_text())
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    if digest != args.expected_sha256 or digest != info['apkSha256']:
        parser.error('The APK differs from the hash approved for signing.')
    if info['signed'] or info['debuggable'] or info['apk'] != apk.name:
        parser.error('Sign only the reviewed unsigned production APK and its matching release.json.')
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk or not os.environ.get(args.password_env):
        parser.error('Set ANDROID_HOME and the signing password environment variable first.')
    signer = Path(sdk) / 'build-tools' / args.build_tools / ('apksigner.bat' if os.name == 'nt' else 'apksigner')
    output = apk.parent / 'mare-launcher.apk'
    subprocess.run([str(signer), 'sign', '--ks', str(args.keystore.resolve()), '--ks-key-alias', args.key_alias,
                    '--ks-pass', 'env:' + args.password_env, '--key-pass', 'env:' + args.password_env,
                    '--out', str(output), str(apk)], check=True)
    verification = subprocess.run([str(signer), 'verify', '--verbose', '--print-certs', str(output)], check=True, capture_output=True, text=True).stdout
    info.update(apk=output.name, apkSha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                apkBytes=output.stat().st_size, signed=True,
                certificateSha256=next(line.split(': ', 1)[1] for line in verification.splitlines() if 'certificate SHA-256 digest:' in line))
    metadata.write_text(json.dumps(info, indent=2) + '\n')
    (apk.parent / 'SHA256SUMS').write_text(info['apkSha256'] + '  ' + output.name + '\n')
    print('Signed locally: ' + str(output))
    print('APK SHA256: ' + info['apkSha256'])
    print('Certificate SHA256: ' + info['certificateSha256'])


if __name__ == '__main__':
    main()
