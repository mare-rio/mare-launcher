import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install as app

IP = '192.0.2.10'
BASE = IP + ':5555'
TLS = IP + ':37123'
PAIR = IP + ':40231'


class Transport:
    """ADB process boundary; connection decisions use the real installer code."""
    def __init__(self, client):
        self.client = client
        self.calls = []
        self.states = {}
        self.services = ''
        self.devices = ''
        self.after_pair = {}
        self.pair_result = 'Successfully paired'

    def run(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if args[0] == 'connect':
            return 'connection attempted'
        if args[0] == 'get-state':
            state = self.states.get(self.client.target, 'error: device not found')
            return state.pop(0) if isinstance(state, list) else state
        if args == ('devices',):
            return self.devices
        if args == ('mdns', 'services'):
            return self.services.pop(0) if isinstance(self.services, list) else self.services
        if args[0] == 'pair':
            self.states.update(self.after_pair)
            return self.pair_result
        raise AssertionError('Unexpected ADB operation: ' + repr(args))


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.client = app.Adb('/adb', BASE)
        self.transport = Transport(self.client)
        for replacement in [patch.object(self.client, 'run', side_effect=self.transport.run),
                            patch.object(app.sys.stdin, 'isatty', return_value=True),
                            patch.object(app.time, 'sleep'),
                            contextlib.redirect_stdout(io.StringIO())]:
            replacement.__enter__()
            self.addCleanup(replacement.__exit__, None, None, None)

    def commands(self, name):
        return [args for args, _ in self.transport.calls if args[0] == name]

    def test_entire_guided_doctor_needs_only_menu_choice_and_ip(self):
        self.transport.states[BASE] = 'device'
        info = {'manufacturer': 'Test', 'model': 'TV', 'api': 30, 'user': '0',
                'device_id': 'fixture', 'home': None, 'webview': 'WebView 151'}
        with tempfile.TemporaryDirectory() as directory, \
             patch('builtins.input', side_effect=['4', IP]) as prompt, \
             patch.object(app, 'find_adb', return_value='/adb'), \
             patch.object(app, 'Adb', return_value=self.client), \
             patch.object(app, 'inspect_tv', return_value=info), \
             patch.object(app, 'install') as install, patch.object(app, 'restore') as restore:
            state = Path(directory) / 'recovery.json'
            app.main(['--state', str(state)])
            self.assertFalse(state.exists())
        self.assertEqual(prompt.call_count, 2)
        self.assertEqual(self.commands('connect'), [('connect', BASE)])
        self.assertFalse(self.commands('pair'))
        install.assert_not_called()
        restore.assert_not_called()

    def test_discovers_connection_port_without_user_questions(self):
        self.transport.services = ('other _adb-tls-connect._tcp 192.0.2.20:37123\n'
                                   'tv _adb-tls-connect._tcp. ' + TLS)
        self.transport.states[TLS] = 'device'
        with patch('builtins.input', side_effect=AssertionError('Unexpected question')):
            self.client.connect(automatic=True)
        self.assertEqual(self.client.target, TLS)
        self.assertEqual(self.commands('connect'), [('connect', BASE), ('connect', TLS)])
        self.assertFalse(self.commands('pair'))

    def test_reuses_transport_only_for_requested_ip(self):
        self.transport.devices = ('List of devices attached\n'
                                  'emulator-5556 device\n192.0.2.20:12345 device\n' + TLS + ' device\n')
        self.transport.states[TLS] = 'device'
        with patch('builtins.input', side_effect=AssertionError('Unexpected question')):
            self.client.connect(automatic=True)
        self.assertEqual(self.commands('connect'), [('connect', BASE), ('connect', TLS)])

    def test_unauthorized_tv_requires_acceptance_not_pairing(self):
        self.transport.states[BASE] = ['error: device unauthorized', 'device']
        with patch('builtins.input', side_effect=['']) as prompt:
            self.client.connect(automatic=True)
        self.assertEqual(prompt.call_count, 1)
        self.assertFalse(self.commands('pair'))
        self.assertFalse(self.commands('mdns'))

    def test_noninteractive_authorization_stops_without_discovery(self):
        self.transport.states[BASE] = 'error: device unauthorized'
        with patch.object(app.sys.stdin, 'isatty', return_value=False), self.assertRaisesRegex(app.InstallError, 'authorisation'):
            self.client.connect(automatic=True)
        self.assertFalse(self.commands('mdns'))

    def test_detected_wireless_tv_needs_code_but_no_port_questions(self):
        self.transport.services = 'tv _adb-tls-connect._tcp ' + TLS + '\npair _adb-tls-pairing._tcp ' + PAIR
        self.transport.after_pair[TLS] = 'device'
        with patch('builtins.input', side_effect=['']) as prompt, \
             patch.object(app.getpass, 'getpass', return_value='123456') as code:
            self.client.connect(automatic=True)
        self.assertEqual(prompt.call_count, 1)  # Open the TV pairing screen.
        code.assert_called_once()
        self.assertEqual(self.commands('pair'), [('pair', PAIR)])
        pair_call = next(kwargs for args, kwargs in self.transport.calls if args[0] == 'pair')
        self.assertEqual(pair_call['stdin'], '123456\n')
        self.assertNotIn('123456', str(self.commands('pair')))
        self.assertEqual(self.client.target, TLS)

    def test_waits_for_pairing_service_even_when_connection_is_already_advertised(self):
        connect = 'tv _adb-tls-connect._tcp ' + TLS
        both = connect + '\npair _adb-tls-pairing._tcp ' + PAIR
        self.transport.services = [connect, connect, both, connect]
        self.transport.after_pair[TLS] = 'device'
        with patch('builtins.input', side_effect=['']), patch.object(app.getpass, 'getpass', return_value='123456'):
            self.client.connect(automatic=True)
        self.assertEqual(self.commands('pair'), [('pair', PAIR)])
        self.assertEqual(self.client.target, TLS)

    def test_no_discovery_requests_ports_only_after_user_opens_pairing(self):
        self.transport.after_pair[TLS] = 'device'
        with patch('builtins.input', side_effect=['pair', '', '40231', '37123']) as prompt, \
             patch.object(app.getpass, 'getpass', return_value='123456'):
            self.client.connect(automatic=True)
        self.assertEqual(prompt.call_count, 4)
        self.assertEqual(self.commands('pair'), [('pair', PAIR)])
        self.assertEqual(self.client.target, TLS)

    def test_wrong_ip_can_be_corrected_without_restarting(self):
        replacement = '192.0.2.20:5555'
        self.transport.states[replacement] = 'device'
        with patch('builtins.input', side_effect=['192.0.2.20']):
            self.client.connect(automatic=True)
        self.assertEqual(self.client.target, replacement)
        self.assertFalse(self.commands('pair'))

    def test_retry_after_turning_debugging_on(self):
        def enable(_):
            self.transport.states[BASE] = 'device'
            return ''
        with patch('builtins.input', side_effect=enable):
            self.client.connect(automatic=True)
        self.assertEqual(self.commands('connect'), [('connect', BASE), ('connect', BASE)])

    def test_back_from_detected_pairing_allows_correcting_tv_ip(self):
        self.transport.services = 'tv _adb-tls-connect._tcp ' + TLS
        self.transport.states['192.0.2.20:5555'] = 'device'
        with patch('builtins.input', side_effect=['back', '192.0.2.20']):
            self.client.connect(automatic=True)
        self.assertEqual(self.client.target, '192.0.2.20:5555')
        self.assertFalse(self.commands('pair'))

    def test_pairing_failure_never_installs_or_echoes_code(self):
        self.transport.services = 'tv _adb-tls-connect._tcp ' + TLS + '\npair _adb-tls-pairing._tcp ' + PAIR
        self.transport.pair_result = 'Pairing failed: 123456'
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), patch('builtins.input', side_effect=['', EOFError()]), \
             patch.object(app.getpass, 'getpass', return_value='123456'), self.assertRaises(EOFError):
            self.client.connect(automatic=True)
        self.assertNotIn('123456', stream.getvalue())
        self.assertFalse(self.commands('install'))
        self.assertFalse(self.commands('shell'))

    def test_cross_tv_pairing_is_rejected_before_code_or_adb(self):
        with patch.object(app.getpass, 'getpass') as code, self.assertRaises(app.InstallError):
            self.client.connect('192.0.2.20:40231')
        code.assert_not_called()
        self.assertEqual(self.transport.calls, [])

    def test_discovery_rejects_unrelated_services_and_invalid_addresses(self):
        services = app.mdns_services('''
other _adb-tls-connect._tcp 192.0.2.20:37123
invalid _adb-tls-connect._tcp 192.0.2.10:0
shell _adb._tcp 192.0.2.10:5555;reboot
host _adb._tcp example.com:5555
http _http._tcp 192.0.2.10:80
tv _adb._tcp 192.0.2.10:5555
tv2 _adb._tcp. 192.0.2.10:5555
''', BASE)
        self.assertEqual(services, {'connect': [BASE], 'pair': [], 'wireless': False})

    def test_discovery_matches_normalized_ipv6(self):
        services = app.mdns_services('tv _adb-tls-connect._tcp [fd00:0::10]:37123\nother _adb._tcp [fd00::20]:5555', '[fd00::10]:5555')
        self.assertEqual(services['connect'], ['[fd00::10]:37123'])


if __name__ == '__main__':
    unittest.main()
