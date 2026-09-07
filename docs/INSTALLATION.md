# Install Maré over your home network

These instructions accompany the complete installation ZIP. The current candidate is local and has not been published. Download instructions will be added when the owner approves a public release.

## Before you start

Use a Windows, macOS or Linux computer on the same trusted home network as the TV. Ethernet and Wi-Fi can be mixed if your router lets the devices talk to each other. Guest Wi-Fi often blocks this connection. Keep the TV awake and its remote nearby.

Install **Python 3.9 or later** from [python.org](https://www.python.org/downloads/) if it is missing. On Windows enable the installer’s PATH option. On Linux your distribution’s Python package is suitable. No Python packages are needed.

Extract the whole ZIP into a folder on your computer. Do not run the installer from inside the compressed ZIP or copy out only the APK. The adjacent `release.json` lets it check the APK’s integrity. A checksum detects changed files; obtain both the bundle and its checksum from a trusted release source.

## 1. Prepare the TV

1. Open the TV’s **Settings**.
2. Look under **System → About** or **Device Preferences → About**.
3. Find **Android TV OS build**, **Build** or **Build number**. Select it seven times until the TV says developer mode is enabled. Enter your TV’s PIN if asked.
4. Return to System or Device Preferences and open **Developer options**.
5. Use the applicable connection method below. Menu names depend on the manufacturer. If the TV is managed by a school, hotel or employer, its administrator may have disabled debugging or launcher replacement.

Do not enable OEM unlocking. Installing a launcher does not require unlocking or erasing the TV.

### TVs with Wireless debugging and a pairing code

Android’s documented wireless pairing support for **TV starts with Android 13**. Some manufacturers differ; use the controls actually present on your TV.

1. Enable **Wireless debugging** and allow it on your home network.
2. On its main screen, note the **IP address and port**. This is the **connection address**.
3. Start the computer installer. Answer yes when asked whether the TV has pairing-code support, and enter that connection address.
4. On the TV choose **Pair device with pairing code**. Keep that screen open.
5. Enter the **pairing address** shown there when the installer requests it, then the six-digit code. The code is entered privately and is not saved.

The pairing port and connection port are different. Pairing authorises your computer; the main-screen address is where it then connects. If the TV closes the pairing screen or the code expires, open a new one and rerun setup. On later updates you normally need only the current connection address.

### TVs with Network / ADB debugging

Many Android 11 televisions expose network ADB through **Network debugging**, **ADB debugging**, or a vendor switch labelled **USB debugging**.

1. Enable the applicable debugging switch.
2. Find the TV’s IP address under **Network → your connection**, or **About → Status**.
3. Enter the IP in the installer. If the TV shows a port, enter `IP:port`; otherwise the installer tries the usual port `5555`.
4. Accept **Allow debugging?** on the TV for your computer. You can select **Always allow** on a computer you trust.

USB debugging alone does **not** turn on network access on all models. If the connection is refused and the TV has no network option, see the troubleshooting section. The installer cannot create a debugging connection that the firmware does not expose.

## 2. Run the guided installer

| Computer | Start setup from the extracted folder |
| --- | --- |
| Windows | Double-click `install.cmd`, or run `py -3 install.py` in Terminal |
| macOS | Open Terminal in the folder and run `sh install.command` |
| Linux | Open a terminal in the folder and run `sh install.sh` |

The installer finds ADB if it is already installed. Otherwise it offers a pinned download from Google and displays Google’s SDK licence before asking you to accept it. It verifies the archive’s SHA-256 before extraction. On ARM Linux, install the distribution’s native `adb` package instead.

After connecting, it prints the TV model, Android version, active profile and current launcher. Check that these describe the TV you intend to change, then accept the installation plan. It saves the original Home selection before making changes and installs Maré without clearing existing app data. Do not close the computer terminal until setup finishes.

Press **Home** on the TV. The installer checks that Maré becomes the foreground Home app. Open **Apps**, hold **OK** on an app and choose **Pin to home**. Repeat for your favourites; up to twelve fit on Home. Streaming apps such as SmartTube or Stremio are installed separately and are not bundled.

Turn debugging off after setup. Maré runs locally and does not need ADB or your computer to stay connected. For a final check, restart the TV normally and press Home again. Firmware updates can reset the Home selection; rerun the installer if that happens.

## If the TV keeps opening Google Home

First try the TV’s own **Default apps → Home app** setting, if present. Some TV firmware reports success for Android’s Home command but continues to open its preinstalled launcher. In that case the installer restores the previous configuration and explains what happened.

The following optional command allows it to disable supported Google Home packages **only if normal selection fails**:

```sh
python3 install.py --target 192.0.2.10 --replace-stock-home
```

Replace `192.0.2.10` with your TV’s address; on Windows use `py -3`. This option can disable Google TV Home, Android TV Home, the older Leanback launcher and Google’s launcher setup companion for the active profile. Their recommendations and setup surfaces will be unavailable while disabled. They are not removed from the TV, and their original enabled states are saved for recovery. The script lists the exact package names before asking you to continue.

There is no general manufacturer-package removal list. If the fallback still fails, setup attempts recovery and leaves Maré installed. Use `--keep-home` to try Maré as a normal app while keeping the current default. Do not disable TV input, settings, update, account or playback services to force a launcher change.

## Updates

Extract the new reviewed bundle and run its installer against the same TV. It uses an in-place Android update and keeps favourites and settings. Keep using the same computer or copy its recovery file to the new computer and pass `--state path/to/file.json`.

Android requires the same signing identity and a compatible version code for an update. `INSTALL_FAILED_UPDATE_INCOMPATIBLE` usually means a different signing key; `INSTALL_FAILED_VERSION_DOWNGRADE` means an older build. The installer will not uninstall your copy to work around either error. Development builds use their own key and do not upgrade production builds.

## Restore and remove

Enable the TV’s debugging connection again. In the extracted folder run:

```sh
python3 install.py restore --target 192.0.2.10
```

It restores the original Home selection and only package states changed by this installer. Maré and its preferences remain installed. To also remove them:

```sh
python3 install.py restore --target 192.0.2.10 --remove
```

This is Home/package-state recovery, not an APK downgrade, a full TV backup or restoration of earlier manual optimisation work. If Maré was already the original Home, the installer will not remove it and leave you without a launcher; select another working Home first.

The recovery record is tied to the TV and active profile using a hashed device identity. Its printed location is usually:

| System | Folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\MareLauncher` |
| macOS | `~/Library/Application Support/Maré Launcher` |
| Linux | `~/.local/state/mare-launcher` or `$XDG_STATE_HOME/mare-launcher` |

Keep the JSON file. It contains the previous Home and affected package states, not account credentials. Do not post it with an issue without inspecting it. A wrong-TV file is rejected. If the network drops during recovery, reconnect and rerun `restore` with the same file; setup refuses further installation while recovery is pending. If the record is lost, select a working Home in TV settings before removing Maré; the installer will not guess which disabled packages belonged to an earlier configuration.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| Connection refused / timed out | Check the current IP, correct port, TV awake, debugging enabled and guest-network isolation. A VPN or firewall on the computer may block local access. |
| `unauthorized` | Accept the TV’s debugging prompt. If it never appears, revoke debugging authorisations in Developer options and reconnect; this also revokes other trusted computers. |
| Pairing succeeds but connection fails | Use the connection port on the main Wireless debugging screen, not the pairing port. |
| No network debugging option | Check the manufacturer’s developer instructions. Standard legacy ADB needs an initial supported USB data connection to run `adb -s USB_SERIAL tcpip 5555`, then a network connection. TV USB ports may be host-only or service-specific; do not connect two host USB-A ports with a passive cable. Without an authorised USB or vendor network route, network installation is unsupported. |
| WebView prerequisite fails / blank launcher | Enable and update Android System WebView through the TV’s Play Store. Restart the TV. The recovery command can run even when WebView is unavailable. |
| HDMI/tuner is missing or will not open | Use the physical Input/Source or Live TV button. Some manufacturers do not expose usable standard input intents. |
| Home resets after a firmware update | Re-enable debugging and rerun installation; retain the recovery file. |
| UI looks soft on a 4K panel | Some TVs render Android’s whole interface at 1080p. A launcher cannot raise a protected manufacturer compositor limit; changing font size or ADB density does not prove 4K output. |

## Advanced commands

```sh
# Connect and inspect prerequisites, without installing.
python3 install.py doctor --target 192.0.2.10

# Show the installation plan without changing TV packages or settings.
python3 install.py --target 192.0.2.10 --dry-run

# Pair first; the code is prompted, never put in command arguments.
python3 install.py --target 192.0.2.10:37123 --pair 192.0.2.10:40231

# Explicit existing ADB, APK and recovery file.
python3 install.py --target 192.0.2.10 --adb /path/to/adb --apk /path/to/mare-launcher.apk --state /path/to/recovery.json
```

`--yes` accepts the displayed installation plan for automation. It does not accept Google’s SDK licence; that requires the separate `--accept-google-license` option. `--serial` selects an already connected USB device or emulator explicitly. The script never silently picks the first connected device.

References: [Android’s official ADB guide](https://developer.android.com/tools/adb), [Google Platform Tools and licence](https://developer.android.com/tools/releases/platform-tools), [Android TV setup](https://developer.android.com/training/tv/get-started/create).
