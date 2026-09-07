import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install as app

STOCK = 'com.google.android.tvlauncher/.MainActivity'


class FakeAdb:
    def __init__(self):
        self.home = STOCK
        self.calls = []
        self.packages = {name: 0 for name in app.GOOGLE_HOMES}
        self.packages[app.GOOGLE_HOMES[-1]] = 3  # A pre-existing disable must be preserved.
        self.fail_install = False
        self.disconnected = False
        self.fail_disable = None

    def run(self, *args, **kwargs):
        self.calls.append(args)
        if self.fail_install:
            raise app.InstallError('Install connection timed out')
        self.home = None  # Android can clear Home when installing a Home candidate.
        return 'Success'

    def shell(self, *args, **kwargs):
        self.calls.append(args)
        if self.disconnected:
            raise app.InstallError('Disconnected')
        if args[:3] == ('cmd', 'package', 'resolve-activity'):
            return self.home or 'android/com.android.internal.app.ResolverActivity'
        if args[:3] == ('cmd', 'package', 'set-home-activity'):
            self.home = args[-1]
            return 'Success'
        if args[:3] == ('pm', 'list', 'packages'):
            return '\n'.join('package:' + p for p in self.packages)
        if args[:2] == ('dumpsys', 'package'):
            return 'User 0: installed=true enabled=' + str(self.packages[args[-1]])
        if args[0] == 'pm' and args[1] in ('default-state', 'enable', 'disable', 'disable-user', 'disable-until-used'):
            package = args[-1]
            if package == self.fail_disable and args[1] == 'disable-user':
                raise app.InstallError('Injected disable failure')
            self.packages[package] = {'default-state': 0, 'enable': 1, 'disable': 2, 'disable-user': 3, 'disable-until-used': 4}[args[1]]
            return 'new state'
        if args[0] == 'input' or args[:2] == ('am', 'start'):
            return ''
        if args[:2] == ('pm', 'uninstall'):
            return 'Success'
        raise AssertionError(args)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.apk = self.directory / 'mare-launcher.apk'
        self.apk.write_bytes(b'a signed APK fixture')
        self.release = {'apk': self.apk.name, 'package': app.PACKAGE, 'signed': True,
                        'version': '0.3.0', 'minSdk': 26, 'apkSha256': hashlib.sha256(self.apk.read_bytes()).hexdigest()}
        (self.directory / 'release.json').write_text(json.dumps(self.release))
        self.state = self.directory / 'state.json'
        self.info = {'device_id': 'tv-one', 'user': '0', 'api': 36, 'home': STOCK}
        self.adb = FakeAdb()
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def install(self, **kwargs):
        return app.install(self.adb, self.info, self.apk, self.state, **kwargs)

    def read_state(self):
        return json.loads(self.state.read_text())

    def test_endpoints_and_rejected_shell_input(self):
        self.assertEqual(app.endpoint('192.0.2.10'), '192.0.2.10:5555')
        self.assertEqual(app.endpoint('[fd00::10]:4567'), '[fd00::10]:4567')
        for invalid in ['192.0.2.10;reboot', 'example.org', '192.0.2.10:0', '192.0.2.10:65536', '-s emulator-5554']:
            with self.subTest(invalid=invalid), self.assertRaises(app.InstallError):
                app.endpoint(invalid)
        with self.assertRaises(app.InstallError):
            app.endpoint('192.0.2.10', None)

    @patch.object(app, 'home_is_running', return_value=True)
    def test_install_and_update_preserve_original_home(self, _):
        self.install()
        self.info['home'] = app.HOME
        self.install()
        self.assertEqual(self.read_state()['previous_home'], STOCK)
        self.assertEqual(self.read_state()['phase'], 'complete')
        self.assertFalse(any(c[:2] == ('pm', 'disable-user') for c in self.adb.calls))

    def test_keep_home_restores_selection_cleared_by_install(self):
        self.install(keep_home=True)
        self.assertEqual(self.adb.home, STOCK)
        self.assertIn(('am', 'start', '--user', '0', '-n', app.HOME), self.adb.calls)

    @patch.object(app, 'home_is_running', return_value=False)
    def test_ignored_home_does_not_silently_debloat(self, _):
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(self.adb.home, STOCK)
        self.assertFalse(any(c[:2] == ('pm', 'disable-user') for c in self.adb.calls))

    @patch.object(app, 'home_is_running', side_effect=[False, True])
    def test_opt_in_google_home_and_exact_restore(self, _):
        before = self.adb.packages.copy()
        self.install(replace_stock=True)
        self.assertEqual(len(self.read_state()['changed_packages']), 3)
        app.restore(self.adb, self.info, self.state)
        self.assertEqual(self.adb.packages, before)
        self.assertEqual(self.adb.home, STOCK)

    @patch.object(app, 'home_is_running', side_effect=[False, True])
    def test_guided_setup_can_replace_google_home_without_extra_command(self, _):
        before = self.adb.packages.copy()
        with patch('builtins.input', return_value='y'):
            self.install(guided=True)
        self.assertEqual(self.read_state()['phase'], 'complete')
        app.restore(self.adb, self.info, self.state)
        self.assertEqual(self.adb.packages, before)
        self.assertEqual(self.adb.home, STOCK)

    @patch.object(app, 'home_is_running', return_value=False)
    def test_guided_decline_or_closed_input_restores_home(self, _):
        for answer in ['', EOFError()]:
            with self.subTest(answer=type(answer).__name__):
                before = self.adb.packages.copy()
                with patch('builtins.input', side_effect=[answer]), self.assertRaises((app.InstallError, EOFError)):
                    self.install(guided=True)
                self.assertEqual(self.adb.home, STOCK)
                self.assertEqual(self.adb.packages, before)
                self.assertEqual(self.read_state()['phase'], 'restored')

    def test_address_typo_can_be_corrected_in_setup(self):
        with patch('builtins.input', side_effect=['192.0.2.', '192.0.2.10']):
            self.assertEqual(app.ask_endpoint('TV address: '), '192.0.2.10:5555')

    def test_bare_ip_is_valid_but_pairing_requires_a_port(self):
        with self.assertRaisesRegex(app.MissingPort, 'IP address is valid'):
            app.endpoint('192.0.2.10', None)
        with self.assertRaises(app.InstallError) as raised:
            app.endpoint('192.0.2.', None)
        self.assertNotIsInstance(raised.exception, app.MissingPort)

    def test_setup_asks_only_for_the_tv_ip(self):
        with patch('builtins.input', side_effect=['192.0.2.10']) as prompt:
            self.assertEqual(app.wizard(), ('192.0.2.10:5555', None))
        self.assertEqual(prompt.call_count, 1)

    def test_manual_port_fallback_retains_ip_and_rejects_another_tv(self):
        with patch('builtins.input', side_effect=['', '0', '65536', '37;reboot', '[fd00::20]:37123', '37123']):
            self.assertEqual(app.ask_tv_port('[fd00::10]:5555', 'Connection port'), '[fd00::10]:37123')

    def test_confirmation_typo_requires_an_explicit_answer(self):
        with patch('builtins.input', side_effect=['yees', 'y']):
            self.assertTrue(app.confirm('Continue?'))

    def test_redirected_terminal_output_has_no_escape_sequences(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            app.ui.panel('Connected TV', ['Untrusted model: \x1b[31mTCL\x1b[0m'])
        self.assertIn('TCL', stream.getvalue())
        self.assertNotIn('\x1b', stream.getvalue())

    def test_guided_restore_menu_dispatches_without_installing(self):
        with patch.object(app.sys.stdin, 'isatty', return_value=True), patch('builtins.input', side_effect=['2', 'y']), \
             patch.object(app, 'wizard', return_value=('192.0.2.10:5555', None)), \
             patch.object(app, 'find_adb', return_value='/adb'), patch.object(app, 'Adb', return_value=self.adb), \
             patch.object(self.adb, 'connect', create=True), \
             patch.object(app, 'inspect_tv', return_value={**self.info, 'manufacturer': 'Test', 'model': 'TV', 'webview': ''}), \
             patch.object(app, 'restore') as restore, patch.object(app, 'install') as install:
            app.main(['--state', str(self.state)])
        restore.assert_called_once_with(self.adb, {**self.info, 'manufacturer': 'Test', 'model': 'TV', 'webview': ''}, self.state.resolve(), False)
        install.assert_not_called()

    @patch.object(app, 'home_is_running', return_value=False)
    def test_partial_disable_failure_restores_already_changed_packages(self, _):
        before = self.adb.packages.copy()
        self.adb.fail_disable = app.GOOGLE_HOMES[1]
        with self.assertRaises(app.InstallError):
            self.install(replace_stock=True)
        self.assertEqual(self.adb.packages, before)
        self.assertEqual(self.adb.home, STOCK)

    @patch.object(app, 'home_is_running', return_value=False)
    def test_unknown_oem_home_is_not_disabled(self, _):
        self.adb.packages = {'vendor.tv.core': 0}
        with self.assertRaises(app.InstallError):
            self.install(replace_stock=True)
        self.assertEqual(self.adb.packages, {'vendor.tv.core': 0})

    def test_install_timeout_attempts_home_recovery(self):
        self.adb.fail_install = True
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(self.read_state()['phase'], 'restored')
        self.assertEqual(self.adb.home, STOCK)

    def test_disconnected_recovery_is_recorded_and_retry_is_blocked(self):
        self.adb.fail_install = True
        self.adb.disconnected = True
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(self.read_state()['phase'], 'recovery-needed')
        count = len(self.adb.calls)
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(len(self.adb.calls), count)
        self.adb.disconnected = False
        app.restore(self.adb, self.info, self.state)
        self.assertEqual(self.read_state()['phase'], 'restored')

    @patch.object(app, 'home_is_running', return_value=True)
    def test_wrong_tv_or_profile_never_mutates(self, _):
        self.install()
        self.info['device_id'] = 'another-tv'
        count = len(self.adb.calls)
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(len(self.adb.calls), count)

    def test_corrupt_apk_is_rejected_before_mutation(self):
        self.apk.write_bytes(b'tampered')
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(self.adb.calls, [])
        self.assertFalse(self.state.exists())

    def test_unsigned_bundle_is_not_installable(self):
        self.release['signed'] = False
        (self.directory / 'release.json').write_text(json.dumps(self.release))
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(self.adb.calls, [])

    def test_missing_original_home_rejected_before_install(self):
        self.info['home'] = None
        with self.assertRaises(app.InstallError):
            self.install()
        self.assertEqual(self.adb.calls, [])
        self.assertFalse(self.state.exists())

    def test_recovery_inspection_does_not_need_working_webview(self):
        replies = {('am', 'get-current-user'): '0', ('getprop', 'ro.build.version.sdk'): '36',
                   ('getprop', 'ro.serialno'): 'test-tv', ('settings', '--user', '0', 'get', 'secure', 'android_id'): 'fixture-id',
                   ('getprop', 'ro.product.manufacturer'): 'Test', ('getprop', 'ro.product.model'): 'TV',
                   ('dumpsys', 'webviewupdate'): 'Current WebView package (name, version): null'}
        def shell(*args):
            if args[:3] == ('cmd', 'package', 'resolve-activity'):
                return STOCK
            return replies[args]
        with patch.object(self.adb, 'shell', side_effect=shell):
            info = app.inspect_tv(self.adb, require_launcher=False)
        self.assertEqual(info['home'], STOCK)
        self.assertEqual(info['user'], '0')

    def test_dry_run_connects_but_does_not_mutate(self):
        with patch.object(app, 'find_adb', return_value='/adb'), patch.object(app, 'Adb', return_value=self.adb), \
             patch.object(self.adb, 'connect', create=True), patch.object(app, 'inspect_tv', return_value={**self.info, 'manufacturer': 'Test', 'model': 'TV', 'webview': 'WebView 143'}):
            app.main(['--target', '192.0.2.10', '--apk', str(self.apk), '--state', str(self.state), '--dry-run'])
        self.assertEqual(self.adb.calls, [])
        self.assertFalse(self.state.exists())

    @patch.object(app, 'home_is_running', return_value=True)
    def test_restore_keeps_app_unless_removal_explicitly_requested(self, _):
        self.install()
        app.restore(self.adb, self.info, self.state)
        self.assertFalse(any(c[:2] == ('pm', 'uninstall') for c in self.adb.calls))
        app.restore(self.adb, self.info, self.state, remove=True)
        self.assertTrue(any(c[:2] == ('pm', 'uninstall') for c in self.adb.calls))

    def test_refuses_to_remove_previous_home_when_it_is_mare(self):
        self.info['home'] = app.HOME
        self.install(keep_home=True)
        with self.assertRaises(app.InstallError):
            app.restore(self.adb, self.info, self.state, remove=True)

    def test_zip_traversal_and_symlink_are_rejected(self):
        for mode in ['traversal', 'symlink', 'windows']:
            archive = self.directory / (mode + '.zip')
            with zipfile.ZipFile(archive, 'w') as z:
                if mode == 'symlink':
                    entry = zipfile.ZipInfo('platform-tools/adb')
                    entry.external_attr = 0o120777 << 16
                    z.writestr(entry, '../../outside')
                else:
                    z.writestr('../outside' if mode == 'traversal' else '..\\outside', 'payload')
            with self.subTest(mode=mode), self.assertRaises(app.InstallError):
                app.safe_extract(archive, self.directory / 'extract')
        self.assertFalse((self.directory.parent / 'outside').exists())

    def test_pairing_code_is_stdin_not_process_arguments(self):
        client = app.Adb('/adb', '192.0.2.10:4567')
        calls = []
        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            return 'Successfully paired' if args[0] == 'pair' else 'device'
        with patch.object(client, 'run', side_effect=fake_run), patch.object(app.getpass, 'getpass', return_value='123456'), patch.object(app.sys.stdin, 'isatty', return_value=True):
            client.connect('192.0.2.10:4568')
        self.assertEqual(calls[0][0], ('pair', '192.0.2.10:4568'))
        self.assertEqual(calls[0][1]['stdin'], '123456\n')
        self.assertNotIn('123456', str(calls[0][0]))

    def test_pairing_refuses_echoing_a_code_in_noninteractive_input(self):
        client = app.Adb('/adb', '192.0.2.10:4567')
        with patch.object(app.sys.stdin, 'isatty', return_value=False), patch.object(app.getpass, 'getpass') as prompt:
            with self.assertRaises(app.InstallError):
                client.connect('192.0.2.10:4568')
            prompt.assert_not_called()


if __name__ == '__main__':
    unittest.main()
