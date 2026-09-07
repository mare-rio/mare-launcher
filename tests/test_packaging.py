import hashlib
import importlib.util
import json
import posixpath
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_release', ROOT / 'scripts/package_release.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackagingTests(unittest.TestCase):
    def test_private_material_excluded_and_bundle_hashes_verified(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            # Mirror only the documented distribution inputs, with an unrelated
            # private key and device evidence present next to them.
            for source in [ROOT / n for n in ['install.py', 'install.cmd', 'install.command', 'install.sh', 'README.md',
                          'LICENSE', 'THIRD_PARTY_NOTICES.md', 'SECURITY.md', 'CONTRIBUTING.md', 'scripts/platform-tools.json']]:
                dest = root / source.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
            for directory in ['docs', 'licenses']:
                for source in (ROOT / directory).rglob('*'):
                    if source.is_file():
                        dest = root / source.relative_to(ROOT)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(source.read_bytes())
            (root / 'private.jks').write_bytes(b'NEVER DISTRIBUTE')
            (root / 'device-evidence.json').write_text('PRIVATE')
            apk = root / 'candidate.apk'
            apk.write_bytes(b'signed production fixture')
            meta = {'apk': apk.name, 'apkSha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
                    'signed': True, 'debuggable': False, 'version': '0.3.0', 'package': 'rio.dan.mare.launcher',
                    'sourceRevision': 'a' * 40, 'sourceDirty': False}
            (root / 'release.json').write_text(json.dumps(meta))
            output = root / 'output.zip'
            package.create_bundle(root, apk, output)
            with zipfile.ZipFile(output) as bundle:
                self.assertNotIn('private.jks', bundle.namelist())
                self.assertNotIn('device-evidence.json', bundle.namelist())
                self.assertIn('mare-launcher.apk', bundle.namelist())
                self.assertIn('START_HERE.html', bundle.namelist())
                self.assertNotIn('docs/CI_SECURITY.md', bundle.namelist())
                self.assertNotIn('CONTRIBUTING.md', bundle.namelist())
                for line in bundle.read('SHA256SUMS').decode().splitlines():
                    digest, path = line.split('  ', 1)
                    self.assertEqual(hashlib.sha256(bundle.read(path)).hexdigest(), digest)
                for name in bundle.namelist():
                    if not name.endswith('.md'):
                        continue
                    for target in re.findall(r'\]\(([^)]+)\)', bundle.read(name).decode()):
                        if ':' in target or target.startswith('#'):
                            continue
                        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target.split('#')[0]))
                        self.assertIn(resolved, bundle.namelist(), 'Broken installation-bundle guide link')
            for field, invalid in [('signed', False), ('debuggable', True), ('sourceDirty', True), ('apkSha256', 'tampered')]:
                broken = {**meta, field: invalid}
                (root / 'release.json').write_text(json.dumps(broken))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    package.create_bundle(root, apk, output)


if __name__ == '__main__':
    unittest.main()
