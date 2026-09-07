# Compatibility and evidence

Maré uses Android TV APIs instead of depending on a TCL launcher service. Its minimum Android API is 26 (Android TV 8.0), and the build targets API 36. A working Android System WebView version 90 or later is required by the installer; use a current provider wherever your manufacturer supports one. API and WebView minimums are implementation requirements, not proof that every older combination has been tested.

## Tested scope

| Environment | Evidence | Limits |
| --- | --- | --- |
| TCL G05 / MT9615, Android 11 | Existing 0.2.0 grid launcher: default Home, D-pad, hold-OK, app launching, Settings, both themes and input discovery | Historical private-preview evidence. The packaged 0.3.0 candidate has not been installed on this TV. |
| TCL G03 / RTD2851M, Android 11 | Same existing 0.2.0 APK: default Home, SmartTube/Stremio favourites, Motion off, app launches and Settings | Historical private-preview evidence; no separate low-end implementation. New package and post-replacement reboot not qualified on this TV. |
| Android TV emulator, Android 16/API 36, WebView 143, 1920×1080 at density 320 | 0.3.0 production candidate: installation from an extracted ZIP, in-place update, Settings via remote, startup as Home after reboot, restoration/removal, no debug access. Development build: native catalog, preference filtering, Back/Menu, app launching and renderer-crash recovery | This image overrides ordinary Home selection and needs the explicit Google Home fallback. Physical HDMI/CEC, power behaviour and visual panel quality are not emulated. |
| Chromium browser on Linux | 960×540 reference geometry, 64-app library, twelve-pin limit, hold-OK, persistence, day/night, Motion, international dates; viewport fitting at 640×360, 1280×720, 1920×1080 and 1024×768 | Browser evidence does not establish Android compositor resolution. |
| Python installer on Linux | Failure/recovery, wrong-device protection, pairing-code handling, checksums, archive safety and bundle exclusion tests | Windows/macOS wrappers and CI matrix are prepared but native execution has not been verified. Actual wireless pairing exchange still needs TV testing. |

The source remains one implementation. Preferences provide a simpler home on slower TVs; the WebView-based launcher is not presented as a measured memory improvement over lightweight native launchers.

## Manufacturer boundaries

- **Default Home:** some firmware forces Google Home. The installer verifies the foreground after pressing Home, then restores on failure. Its optional Google Home fallback is explicit and reversible. Locked-down OEM/managed models may not allow replacement at all.
- **Network ADB:** Android TV 13+ documents wireless pairing. Older vendor network-debugging switches vary; some TVs require a supported USB bootstrap and some expose neither route.
- **Inputs:** HDMI/tuner discovery and opening depend on the manufacturer’s standard Android TV integration. The remote’s Source key may be intercepted by the TV even when Maré is foreground. Use the physical selector when needed.
- **4K panels:** Maré preserves high-resolution sand and scales the layout to the viewport Android supplies. Some TVs compose the entire Android UI at 1080p before scaling to a 4K panel. This protected manufacturer pipeline is outside a launcher’s control; the installer does not change display density or firmware.
- **Boot and updates:** Android normally starts the selected Home. Firmware updates, managed profiles or vendor services may reset it. Verify a normal restart on your own TV and keep the installer’s recovery file.

Compatibility reports should include model, Android version, WebView version, launcher revision, connection method and observed Home/input behaviour. Do not include private device dumps or account data.
