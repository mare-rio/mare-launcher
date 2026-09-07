#!/usr/bin/env python3
"""Guided network ADB installation and recovery. Python 3.9+, no Python packages."""
import argparse
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import textwrap
import urllib.request
import urllib.parse
import zipfile

ROOT = Path(__file__).resolve().parent
PACKAGE = 'rio.dan.mare.launcher'
HOME = PACKAGE + '/.LauncherActivity'
GOOGLE_HOMES = ('com.google.android.apps.tv.launcherx', 'com.google.android.tvlauncher',
                'com.google.android.leanbacklauncher', 'com.google.android.tungsten.setupwraith')


class InstallError(Exception):
    pass


class MissingPort(InstallError):
    pass


class Terminal:
    """Small, dependency-free terminal presentation; plain output when redirected."""
    plain = False

    @staticmethod
    def clean(value):
        value = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(value))
        return re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', value)

    def styled(self, value, colour='36'):
        value = self.clean(value)
        colour_ok = sys.stdout.isatty() and not self.plain and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb'
        if colour_ok and os.name == 'nt':
            # Older Windows consoles require enabling virtual terminal output.
            import ctypes
            handle = ctypes.windll.kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            colour_ok = bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)) and
                             ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 4))
        return '\x1b[' + colour + 'm' + value + '\x1b[0m' if colour_ok else value

    def panel(self, title, lines):
        width = max(24, min(shutil.get_terminal_size((88, 24)).columns, 96) - 2)
        unicode_ok = not self.plain and sys.stdout.isatty()
        try:
            '╭─╮│╰╯'.encode(sys.stdout.encoding or 'utf-8')
        except UnicodeEncodeError:
            unicode_ok = False
        tl, h, tr, v, bl, br = ('╭', '─', '╮', '│', '╰', '╯') if unicode_ok else ('+', '-', '+', '|', '+', '+')
        print()
        print(self.styled(tl + h * (width - 2) + tr))
        for row, heading in [(title, True), ('', False)] + [(line, False) for line in lines]:
            for part in textwrap.wrap(self.clean(row), width - 4, replace_whitespace=True) or ['']:
                print(self.styled(v) + ' ' + self.styled(part.ljust(width - 4), '1;36' if heading else '0') + ' ' + self.styled(v))
        print(self.styled(bl + h * (width - 2) + br))

    def step(self, number, title):
        print('\n' + self.styled(str(number) + ' / 4  ' + title, '1;36'))

    def success(self, message):
        print('\n' + self.styled('Done  ', '1;32') + self.clean(message))

    def prompt(self, message):
        return input(self.styled(message, '1;36'))


ui = Terminal()


def confirm(question, yes=False):
    if yes:
        return True
    while True:
        answer = ui.prompt(question + ' [y/N] ').strip().lower()
        if answer in ('y', 'yes'):
            return True
        if answer in ('', 'n', 'no'):
            return False
        print('Type y for yes or n for no, then press Enter.')


def data_dir():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'MareLauncher'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/Maré Launcher'
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'mare-launcher'


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def endpoint(value, default_port=5555):
    """Accept IP addresses only; never interpolate arbitrary text into remote commands."""
    value = value.strip()
    if value.startswith('['):
        match = re.fullmatch(r'\[([^\]]+)\](?::(\d+))?', value)
        if not match:
            raise InstallError('Use [IPv6 address]:port, for example [fd00::10]:5555.')
        host, port = match.groups()
    elif value.count(':') == 1:
        host, port = value.split(':')
    else:
        host, port = value, None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise InstallError('Enter a valid TV IP address, for example 192.0.2.10.') from None
    if port is None and default_port is None:
        raise MissingPort('This IP address is valid. Wireless debugging also needs the port shown after the colon on the TV.')
    try:
        number = int(port) if port is not None else default_port
        if not 1 <= number <= 65535:
            raise ValueError()
    except ValueError:
        raise InstallError('The port must be a number from 1 to 65535, as shown on the TV.') from None
    return ('[' + str(address) + ']' if address.version == 6 else str(address)) + ':' + str(number)


def endpoint_host(value):
    return endpoint(value).rsplit(':', 1)[0]


def mdns_services(output, target):
    """Use only numeric service addresses belonging to the requested TV."""
    services = {'connect': [], 'pair': [], 'wireless': False}
    kinds = {'_adb._tcp': 'connect', '_adb-tls-connect._tcp': 'connect',
             '_adb-tls-pairing._tcp': 'pair'}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1].rstrip('.') not in kinds:
            continue
        kind = fields[1].rstrip('.')
        try:
            address = endpoint(fields[2], None)
        except InstallError:
            continue
        if endpoint_host(address) != endpoint_host(target):
            continue
        group = services[kinds[kind]]
        if address not in group:
            group.append(address)
        services['wireless'] |= kind.startswith('_adb-tls-')
    return services


def safe_extract(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        if sum(item.file_size for item in bundle.infolist()) > 128 * 1024 * 1024:
            raise InstallError('Platform Tools archive is unexpectedly large.')
        for item in bundle.infolist():
            target = (destination / item.filename).resolve()
            if '\\' in item.filename or not target.is_relative_to(destination.resolve()):
                raise InstallError('Unsafe path in Platform Tools archive.')
            if stat.S_ISLNK(item.external_attr >> 16):
                raise InstallError('Unexpected symbolic link in Platform Tools archive.')
        bundle.extractall(destination)
    executable = destination / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
    if not executable.is_file():
        raise InstallError('Google archive did not contain adb.')
    if os.name != 'nt':
        executable.chmod(0o755)
    return executable


def find_adb(explicit=None, accept_license=False):
    if explicit:
        result = shutil.which(explicit) or (str(Path(explicit).resolve()) if Path(explicit).is_file() else None)
        if not result:
            raise InstallError('ADB was not found at the supplied path.')
        return result
    found = shutil.which('adb')
    if found:
        return found
    config = json.loads((ROOT / 'scripts/platform-tools.json').read_text())
    host = 'windows' if os.name == 'nt' else 'darwin' if sys.platform == 'darwin' else 'linux'
    cache = data_dir() / 'tools' / config['version']
    executable = cache / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
    if executable.exists():
        return str(executable)
    if host == 'linux' and platform.machine().lower() not in ('x86_64', 'amd64'):
        raise InstallError('On ARM Linux, install your distribution’s native adb package, then run this installer again.')
    print('ADB connects your computer to the TV. It is missing on this computer.')
    print('The installer can download Google Platform Tools ' + config['version'] + '.')
    print('Google SDK licence: ' + config['license'])
    if not confirm('Do you accept Google’s SDK licence and want to download Platform Tools?', accept_license):
        raise InstallError('Install ADB yourself and rerun with --adb /path/to/adb.')
    item = config['archives'][host]
    print('Downloading Google connection tools; the archive will be checked before use...', flush=True)
    url = urllib.parse.urlparse(item['url'])
    if url.scheme != 'https' or url.netloc != 'dl.google.com' or not url.path.startswith('/android/repository/'):
        raise InstallError('Platform Tools must come from Google’s official HTTPS repository.')
    with urllib.request.urlopen(item['url'], timeout=45) as response:
        if urllib.parse.urlparse(response.geturl()).netloc != 'dl.google.com':
            raise InstallError('Unexpected redirect while downloading Platform Tools.')
        payload = response.read(item['size'] + 1)
    if len(payload) != item['size'] or hashlib.sha256(payload).hexdigest() != item['sha256']:
        raise InstallError('Platform Tools checksum failed. Nothing was installed.')
    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache.parent) as tmp:
        tmp = Path(tmp)
        archive = tmp / 'download.zip'
        archive.write_bytes(payload)
        extracted = tmp / 'unpacked'
        extracted.mkdir()
        safe_extract(archive, extracted)
        # Only promote a completely downloaded, verified and extracted archive.
        os.replace(extracted, cache)
    return str(executable)


class Adb:
    def __init__(self, executable, target):
        self.executable, self.target = str(executable), target

    def run(self, *args, timeout=30, checked=True, stdin=None, targeted=True):
        command = [self.executable] + (['-s', self.target] if targeted else []) + list(map(str, args))
        try:
            result = subprocess.run(command, input=stdin, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise InstallError('The TV did not respond in time. Keep it awake and check the connection. You can rerun safely.') from None
        output = (result.stdout + result.stderr).strip()
        if checked and (result.returncode or re.search(r'(^|\n)(Error|Failure|Exception|SecurityException)', output)):
            raise InstallError(output or 'ADB command failed.')
        return output

    def shell(self, *args, **kwargs):
        return self.run('shell', shlex.join(map(str, args)), **kwargs)

    def pair(self, address):
        address = endpoint(address, None)
        if endpoint_host(address) != endpoint_host(self.target):
            raise InstallError('The pairing address must belong to the TV IP you entered.')
        if not sys.stdin.isatty():
            raise InstallError('Pairing needs an interactive terminal so the code can be entered privately. Rerun in Terminal.')
        while True:
            code = getpass.getpass('Six-digit pairing code shown on the TV: ').strip()
            if re.fullmatch(r'[0-9]{6}', code):
                break
            print('Enter the six digits from the TV pairing screen.')
        # A pairing code is passed through stdin, never process arguments or a log.
        output = self.run('pair', address, targeted=False, stdin=code + '\n', checked=False)
        if 'Successfully paired' not in output:
            raise InstallError('Pairing failed. Open a new pairing-code screen on the TV and try again.')

    def try_connection(self):
        if not self.target.startswith('emulator-') and ':' in self.target:
            try:
                self.run('connect', self.target, targeted=False, checked=False, timeout=5)
            except InstallError:
                pass  # A timed-out connect can still leave an authorisation prompt on the TV.
        try:
            state = self.run('get-state', checked=False, timeout=5)
        except InstallError:
            return False
        while 'unauthorized' in state:
            print('On the TV, accept “Allow debugging?” for this computer. Select Always allow if it is your computer.')
            if not sys.stdin.isatty():
                raise InstallError('TV authorisation is required. Accept its prompt, then rerun.')
            ui.prompt('Press Enter here after accepting on the TV. ')
            state = self.run('get-state', checked=False, timeout=5)
        return state.strip() == 'device'

    def discover(self, wait=False, required=None):
        # Give a newly started ADB server / pairing screen time to announce itself.
        services = {'connect': [], 'pair': [], 'wireless': False}
        for attempt in range(3 if wait else 1):
            if attempt:
                time.sleep(1)
            try:
                output = self.run('mdns', 'services', targeted=False, checked=False, timeout=5)
            except InstallError:
                break
            services = mdns_services(output, self.target)
            if (services[required] if required else services['connect'] or services['pair']):
                break
        return services

    def try_addresses(self, addresses):
        original = self.target
        for address in dict.fromkeys(addresses):
            if endpoint_host(address) != endpoint_host(original):
                continue
            self.target = endpoint(address, None)
            if self.try_connection():
                return True
        self.target = original
        return False

    def known_addresses(self):
        """Reuse numeric network transports for this IP, never select another device."""
        try:
            output = self.run('devices', targeted=False, checked=False, timeout=5)
        except InstallError:
            return []
        addresses = []
        for line in output.splitlines():
            fields = line.split()
            if len(fields) != 2 or fields[1] != 'device':
                continue
            try:
                address = endpoint(fields[0], None)
            except InstallError:
                continue
            if endpoint_host(address) == endpoint_host(self.target):
                addresses.append(address)
        return addresses

    def guided_pairing(self, services):
        ui.panel('Allow this computer to connect', [
            'On the TV, open Settings > Developer options > Wireless debugging.',
            'Choose Pair device with pairing code and keep that screen open.',
            'Setup will look up the connection details and ask for the six-digit code.'
        ])
        if ui.prompt('Press Enter when the pairing code is visible (or type back): ').strip().lower() == 'back':
            return False
        # The pairing port can change every time the TV opens this screen.
        fresh = self.discover(wait=True, required='pair')
        pairs = fresh['pair']
        if len(pairs) == 1:
            pair = pairs[0]
        else:
            print('Automatic discovery could not identify one pairing port for this TV.')
            print('On the pairing-code screen, copy the number after the colon in IP address & port.')
            pair = ask_tv_port(self.target, 'Pairing port')
            if pair is None:
                return False
        try:
            self.pair(pair)
        except InstallError as error:
            print(error)
            return False
        print('Paired. Finding the TV connection...')
        after = self.discover(wait=True, required='connect')
        addresses = after['connect'] + fresh['connect'] + services['connect'] + self.known_addresses()
        if self.try_addresses(addresses + [self.target]):
            return True
        if addresses:
            print('The TV paired, but its connection is not responding yet. Keep Wireless debugging enabled and retry.')
            return False
        print('Your network is not reporting the TV connection port automatically.')
        print('Close the pairing-code screen. On the MAIN Wireless debugging screen, copy the port after the colon.')
        address = ask_tv_port(self.target, 'Connection port')
        if address is None:
            return False
        self.target = address
        return self.try_connection()

    def connect_automatically(self):
        while True:
            print('Looking for your TV at ' + endpoint_host(self.target) + '...', flush=True)
            if self.try_connection():
                return
            if self.try_addresses(self.known_addresses()):
                return
            services = self.discover(wait=True)
            if self.try_addresses(services['connect']):
                return
            if not sys.stdin.isatty():
                raise InstallError('The TV is not connected. Enable debugging and run setup interactively for connection help.')
            if services['wireless'] and self.guided_pairing(services):
                return
            ui.panel('The TV has not connected yet', [
                'Keep the TV awake and check that debugging is switched on in Developer options.',
                'Check its IP in Settings > Network or About > Status. Use the same home network, not guest Wi-Fi.',
                'If Wireless debugging shows a pairing code, type pair below. If it shows IP address & port, you can enter that full address.',
                'If this TV has no network debugging support, see docs/INSTALLATION.md > Troubleshooting.'
            ])
            while True:
                answer = ui.prompt('Press Enter to retry, enter the TV IP, or type pair: ').strip()
                if not answer:
                    break
                if answer.lower() == 'pair':
                    if self.guided_pairing(services):
                        return
                    continue
                try:
                    self.target = endpoint(answer)
                    break
                except InstallError as error:
                    print(error)

    def connect(self, pair=None, automatic=False):
        if pair:
            self.pair(pair)
        elif automatic:
            return self.connect_automatically()
        print('Connecting to ' + self.target + '...')
        if not self.try_connection():
            raise InstallError('TV is not connected. Check its IP, debugging switch and same-network connection.')


def component(output):
    values = re.findall(r'(?m)^\s*([A-Za-z_][\w.]*/[\w.$]+)\s*$', output)
    return values[-1] if values and not values[-1].startswith('android/') else None


def current_home(adb, user):
    return component(adb.shell('cmd', 'package', 'resolve-activity', '--brief', '--user', user,
                               '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME'))


def inspect_tv(adb, require_launcher=True):
    user = adb.shell('am', 'get-current-user').strip()
    if not user.isdigit():
        raise InstallError('Cannot determine the active TV profile.')
    api = adb.shell('getprop', 'ro.build.version.sdk')
    if not api.isdigit() or (require_launcher and int(api) < 26):
        raise InstallError('Maré requires Android TV 8.0 or later.')
    if require_launcher and 'android.software.leanback' not in adb.shell('pm', 'list', 'features'):
        raise InstallError('This device does not report Android TV / Google TV support.')
    serial = adb.shell('getprop', 'ro.serialno')
    android_id = adb.shell('settings', '--user', user, 'get', 'secure', 'android_id')
    identity = '|'.join(x for x in (serial, android_id) if x and x not in ('null', 'unknown'))
    if not identity:
        raise InstallError('Cannot identify this TV reliably enough to save a recovery record.')
    view = adb.shell('dumpsys', 'webviewupdate')
    provider = re.search(r'Current WebView package[^\n]*', view)
    if require_launcher and (not provider or 'null' in provider.group(0)):
        raise InstallError('No active Android System WebView. Enable or update it through the TV Play Store first.')
    version = re.search(r'\b(\d{2,3})\.\d+\.', provider.group(0)) if provider else None
    if require_launcher and version and int(version.group(1)) < 90:
        raise InstallError('Update Android System WebView through the TV Play Store before installing Maré (version 90 or later).')
    return {'device_id': hashlib.sha256((identity + '|' + user).encode()).hexdigest(), 'user': user,
            'manufacturer': adb.shell('getprop', 'ro.product.manufacturer'),
            'model': adb.shell('getprop', 'ro.product.model'), 'api': int(api),
            'home': current_home(adb, user), 'webview': provider.group(0) if provider else 'No active WebView'}


def enabled_state(adb, package, user):
    data = adb.shell('dumpsys', 'package', package)
    result = re.search(r'User ' + re.escape(str(user)) + r':[^\n]*enabled=(\d+)', data)
    if not result:
        raise InstallError('Cannot determine the package state for ' + package)
    return int(result.group(1))


def set_enabled(adb, package, user, value):
    commands = {0: 'default-state', 1: 'enable', 2: 'disable', 3: 'disable-user', 4: 'disable-until-used'}
    if value not in commands or not re.fullmatch(r'[A-Za-z_][\w.]*', package):
        raise InstallError('Invalid saved package state.')
    adb.shell('pm', commands[value], '--user', user, package)


def same_home(value):
    return value in (HOME, PACKAGE + '/' + PACKAGE + '.LauncherActivity')


def home_is_running(adb, user):
    adb.shell('input', 'keyevent', 'KEYCODE_HOME')
    for _ in range(4):
        time.sleep(1)
        activity = adb.shell('dumpsys', 'activity', 'activities')
        foreground = [line for line in activity.splitlines() if 'mResumedActivity' in line or 'topResumedActivity' in line]
        if any(PACKAGE + '/' in line for line in foreground) and same_home(current_home(adb, user)):
            return True
    return False


def load_state(path, info):
    if not path.exists():
        return None
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise InstallError('The recovery file is unreadable. Keep it and resolve this before making more changes.') from None
    if saved.get('schema') != 1 or saved.get('device_id') != info['device_id'] or saved.get('user') != info['user']:
        raise InstallError('This recovery file belongs to a different TV or profile. No changes made.')
    return saved


def verify_apk(apk):
    manifest = apk.parent / 'release.json'
    if not apk.is_file() or not manifest.is_file():
        raise InstallError('Use the complete Maré installation ZIP: the APK and release.json must be together. Run install.cmd on Windows, or sh install.sh on macOS/Linux.')
    info = json.loads(manifest.read_text(encoding='utf-8'))
    if info.get('package') != PACKAGE or info.get('apk') != apk.name or not info.get('signed'):
        raise InstallError('This is not a signed Maré installation bundle.')
    if hashlib.sha256(apk.read_bytes()).hexdigest() != info.get('apkSha256'):
        raise InstallError('APK checksum failed. Download the installation ZIP again; nothing was installed.')
    return info


def restore(adb, info, state_path, remove=False):
    saved = load_state(state_path, info)
    if not saved:
        raise InstallError('No recovery record for this TV. The installer will not guess which system apps to enable.')
    previous = saved.get('previous_home')
    if not previous or not component(previous):
        raise InstallError('There was no explicit Home selection to restore. Choose Home in TV settings before removing Maré.')
    if remove and same_home(previous):
        raise InstallError('Maré was already the default before this installation. Choose another Home before removing it.')
    saved['phase'] = 'restoring'
    atomic_json(state_path, saved)
    for package, original in saved['changed_packages'].items():
        if package not in GOOGLE_HOMES:
            raise InstallError('Recovery record contains an unsupported system package. Inspect it before proceeding.')
        set_enabled(adb, package, info['user'], original)
    adb.shell('cmd', 'package', 'set-home-activity', '--user', info['user'], previous)
    if current_home(adb, info['user']) != previous:
        raise InstallError('Previous Home could not be restored. Maré remains installed; keep the recovery file.')
    adb.shell('input', 'keyevent', 'KEYCODE_HOME')
    if remove:
        output = adb.shell('pm', 'uninstall', '--user', info['user'], PACKAGE)
        if 'Success' not in output:
            raise InstallError('Home was restored, but Android did not remove Maré: ' + output)
    saved['phase'] = 'restored'
    atomic_json(state_path, saved)
    ui.success('Previous Home restored.' + (' Maré has been removed.' if remove else ' Maré stays installed.'))


def install(adb, info, apk, state_path, keep_home=False, replace_stock=False, guided=False):
    release = verify_apk(apk)
    if info['api'] < release['minSdk']:
        raise InstallError('This release needs a newer Android version.')
    saved = load_state(state_path, info)
    if saved and saved['phase'] in ('restoring', 'recovery-needed'):
        raise InstallError('An earlier operation needs recovery. Open setup and choose Restore first, or use the restore command.')
    if not keep_home and not (saved['previous_home'] if saved and saved['phase'] != 'restored' else info['home']):
        raise InstallError('Choose a default Home in TV settings first so it can be restored later, or use --keep-home.')
    if not saved or saved['phase'] == 'restored':
        saved = {'schema': 1, 'device_id': info['device_id'], 'user': info['user'],
                 'previous_home': info['home'], 'changed_packages': {}, 'phase': 'prepared'}
        atomic_json(state_path, saved)
    ui.step(4, 'Install Maré and set Home')
    print('Recovery record: ' + str(state_path))
    # A Home-candidate update can clear Android's preference, even if the
    # connection drops before its success response reaches the computer.
    saved['phase'] = 'installing'
    atomic_json(state_path, saved)
    try:
        output = adb.run('install', '--no-incremental', '-r', '--user', info['user'], str(apk), timeout=120)
        if 'Success' not in output:
            raise InstallError('Android did not install the APK: ' + output)
        saved['phase'] = 'installed'
        saved['version'] = release['version']
        atomic_json(state_path, saved)
        if keep_home:
            if info['home']:
                adb.shell('cmd', 'package', 'set-home-activity', '--user', info['user'], info['home'])
            adb.shell('am', 'start', '--user', info['user'], '-n', HOME)
        else:
            if not saved['previous_home']:
                raise InstallError('Choose a default Home in TV settings first so it can be restored later, or use --keep-home.')
            adb.shell('cmd', 'package', 'set-home-activity', '--user', info['user'], HOME)
            if not home_is_running(adb, info['user']):
                if guided and not replace_stock:
                    print('\nYour TV keeps opening Google Home instead of Maré.')
                    print('Setup can turn off Google Home and its launcher setup companion for this profile.')
                    print('Your streaming apps stay installed. You can turn Google Home back on by running setup again and choosing Restore.')
                    replace_stock = confirm('Allow setup to turn off Google Home if it is present?')
                if not replace_stock:
                    raise InstallError('This TV did not keep Maré as Home. Recovery is being applied. '
                                       'If it uses Google TV Home, you may rerun with --replace-stock-home; see docs/INSTALLATION.md.')
                installed = set(adb.shell('pm', 'list', 'packages', '--user', info['user']).splitlines())
                candidates = [p for p in GOOGLE_HOMES if 'package:' + p in installed]
                if not candidates:
                    raise InstallError('No supported Google Home package found. OEM-specific Home restrictions need manual guidance.')
                for package in candidates:
                    old = enabled_state(adb, package, info['user'])
                    if old in (2, 3, 4):
                        continue
                    saved['changed_packages'].setdefault(package, old)
                    atomic_json(state_path, saved)  # Record intent before touching the package.
                    adb.shell('pm', 'disable-user', '--user', info['user'], package)
                adb.shell('cmd', 'package', 'set-home-activity', '--user', info['user'], HOME)
                if not home_is_running(adb, info['user']):
                    raise InstallError('Firmware still overrides Home; restoring the prior configuration.')
        saved['phase'] = 'complete'
        atomic_json(state_path, saved)
    except (InstallError, KeyboardInterrupt, EOFError):
        try:
            restore(adb, info, state_path)
        except (InstallError, KeyboardInterrupt) as error:
            saved['phase'] = 'recovery-needed'
            atomic_json(state_path, saved)
            print('Automatic recovery could not finish: ' + str(error), file=sys.stderr)
            print('Keep the recovery file and rerun restore when the TV is connected.', file=sys.stderr)
        raise
    ui.success('Maré ' + release['version'] + ' installed. ' + ('Previous Home retained.' if keep_home else 'Home now opens Maré.'))
    print('In Maré: Apps > hold OK on an app > Pin to home. Settings > Motion can reduce animation.')
    print('You can now turn debugging off on the TV. Turn it on again for updates or recovery.')


def choose_action():
    ui.panel('Maré Launcher · TV setup', [
        'A quieter Home screen for your television.',
        'This terminal guides you through TV preparation, connection and installation.',
        'Use the same computer to restore your previous Home later.',
        'Type a number and press Enter. Press Ctrl+C at any time to stop.'
    ])
    print('1. Install or update Maré (press Enter)')
    print('2. Restore my previous Home screen')
    print('3. Restore my previous Home screen and remove Maré')
    print('4. Check my TV connection without changing anything')
    while True:
        choice = ui.prompt('Choose 1–4: ').strip() or '1'
        if choice in ('1', '2', '3', '4'):
            return {'1': 'install', '2': 'restore', '3': 'restore', '4': 'doctor'}[choice], choice == '3'
        print('Type 1, 2, 3 or 4, then press Enter.')


def ask_endpoint(prompt, default_port=5555):
    while True:
        value = ui.prompt(prompt).strip()
        try:
            return endpoint(value, default_port)
        except InstallError as error:
            print(str(error) + ' Try again, or press Ctrl+C to cancel.')


def ask_tv_port(target, label):
    """Last-resort input when network discovery is unavailable; retain the TV IP."""
    while True:
        value = ui.prompt(label + ' shown on the TV (or back): ').strip()
        if value.lower() == 'back':
            return None
        try:
            address = endpoint(endpoint_host(target), int(value)) if re.fullmatch(r'[0-9]{1,5}', value) else endpoint(value, None)
            if endpoint_host(address) != endpoint_host(target):
                raise InstallError('Use the port for the TV IP you already entered.')
            return address
        except InstallError as error:
            print(str(error) + ' Enter the port number, or type back to return to connection checks.')


def wizard():
    ui.step(1, 'Prepare your TV')
    ui.panel('Enable the TV connection', [
        'Connect the TV and this computer to the same home network. Wi-Fi or Ethernet both work. Keep the TV awake.',
        '1. Open Settings > System > About (or Device Preferences > About).',
        '2. Select Android TV OS build / Build number seven times, until developer mode is enabled.',
        '3. Go back and open Developer options.',
        '4. Turn on Network debugging or ADB debugging. On many TCL TVs, the switch is called USB debugging: turn it on even though setup uses the network.',
        '5. If the TV offers Wireless debugging instead, turn it on and allow your home network. Keep that screen open; setup will handle the connection.',
        'Leave OEM unlocking alone. When the TV asks Allow debugging?, accept with your remote.'
    ])
    ui.step(2, 'Connect to your TV')
    ui.panel('Find the TV IP address', [
        'On the TV, open Settings > Network & Internet > your connected Wi-Fi or Ethernet network.',
        'Look for IP address. It may also be under Settings > About > Status.',
        'Type that address below, for example 192.0.2.10. Setup will find the connection automatically.'
    ])
    return ask_endpoint('TV IP address: '), None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['install', 'restore', 'doctor'])
    device = parser.add_mutually_exclusive_group()
    device.add_argument('--target', help='TV network IP[:connection port]')
    device.add_argument('--serial', help='Explicit already-connected USB or emulator serial (advanced)')
    parser.add_argument('--pair', help='IP:pairing port; code is prompted privately')
    parser.add_argument('--adb', help='Path to an existing adb executable')
    parser.add_argument('--apk', type=Path)
    parser.add_argument('--state', type=Path, help='Override the local recovery file path')
    parser.add_argument('--yes', action='store_true', help='Accept the displayed installation/restoration plan')
    parser.add_argument('--accept-google-license', action='store_true', help='Explicitly accept Google SDK terms if ADB must be downloaded')
    parser.add_argument('--keep-home', action='store_true', help='Install/open Maré while retaining the current default Home')
    parser.add_argument('--replace-stock-home', action='store_true', help='If necessary, allow reversible disabling of supported Google Home packages')
    parser.add_argument('--remove', action='store_true', help='With restore, also uninstall Maré for this profile')
    parser.add_argument('--plain', action='store_true', help='Plain terminal output without colours or box-drawing characters')
    parser.add_argument('--dry-run', action='store_true', help='Connect and inspect; make no TV configuration or package changes')
    args = parser.parse_args(argv)
    ui.plain = args.plain
    guided = not (args.target or args.serial)
    if guided and sys.stdin.isatty() and args.action is None:
        args.action, remove = choose_action()
        args.remove = args.remove or remove
    args.action = args.action or 'install'
    if args.remove and args.action != 'restore':
        parser.error('--remove is only valid with restore')
    if args.pair and not args.target:
        parser.error('--pair requires --target with the separate connection port')
    if args.target:
        target, pair = endpoint(args.target), args.pair
    elif args.serial:
        if not re.fullmatch(r'[\w.:-]+', args.serial):
            parser.error('Invalid device serial')
        target, pair = args.serial, None
    else:
        if not sys.stdin.isatty():
            parser.error('Supply --target IP[:port], or run interactively for guided setup')
        target, pair = wizard()
    adb = Adb(find_adb(args.adb, args.accept_google_license), target)
    adb.connect(pair, automatic=not args.serial and not pair)
    info = inspect_tv(adb, require_launcher=args.action != 'restore')
    ui.step(3, 'Check your TV')
    ui.panel('Connected television', [
        'TV: ' + info['manufacturer'] + ' ' + info['model'],
        'Android API: ' + str(info['api']) + '    Profile: ' + info['user'],
        'Current Home: ' + (info['home'] or 'not explicitly selected'),
        info['webview']
    ])
    state_path = (args.state or data_dir() / (info['device_id'][:24] + '.json')).expanduser().resolve()
    load_state(state_path, info)  # Reject a mismatched file before any mutation.
    if args.action == 'doctor':
        ui.step(4, 'Connection ready')
        ui.success('Your TV is connected and meets the launcher prerequisites. No TV settings or apps were changed.')
        print('To install Maré, run setup again and choose 1. Recovery file location: ' + str(state_path))
        return
    apk = args.apk or (ROOT / 'mare-launcher.apk' if (ROOT / 'mare-launcher.apk').exists() else ROOT / 'dist/mare-launcher.apk')
    if args.action == 'install':
        release = verify_apk(apk)
        print('Install Maré ' + release['version'] + (' (development build)' if release.get('debuggable') else '') + '.')
        print('Retain current Home.' if args.keep_home else 'Set Maré as the default Home.')
        if args.replace_stock_home:
            print('If Home is overridden, allow disabling only these Google Home packages for this profile: ' + ', '.join(GOOGLE_HOMES))
    else:
        ui.step(4, 'Restore your previous Home')
        print('Restore saved Home and package states.' + (' Also remove Maré and its preferences from this profile.' if args.remove else ' Keep Maré installed.'))
    if args.dry_run:
        print('Dry run complete; no TV configuration or packages changed.')
        return
    if not confirm('Continue on this TV?', args.yes):
        print('Cancelled; no TV changes made.')
        return
    if args.action == 'install':
        install(adb, info, apk.resolve(), state_path, args.keep_home, args.replace_stock_home, guided=guided)
    else:
        restore(adb, info, state_path, args.remove)


if __name__ == '__main__':
    if sys.version_info < (3, 9):
        sys.exit('Install Python 3.9 or later before running Maré setup.')
    try:
        main()
    except (InstallError, OSError, ValueError, KeyboardInterrupt, EOFError) as error:
        print('\nSetup stopped: ' + (str(error) or 'cancelled'), file=sys.stderr)
        sys.exit(1)
