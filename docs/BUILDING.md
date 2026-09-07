# Build, inspect and package locally

The source checkout includes all code and design assets required for the launcher. The installation ZIP is for installing; obtain the source checkout to build it. No private Maré registry, checkout, service or account is needed. The APK contains Java bytecode and local web assets, so one build serves ARM, ARM64 and x86 Android TV devices supported by Android and their WebView provider.

## Tools

- Python 3.9 or later.
- Node.js 22 and npm.
- Java 21 JDK (`java`, `javac` and `keytool` on PATH).
- [Android SDK command-line tools](https://developer.android.com/studio#command-tools), platform 36 and build-tools 36.0.0. Set `ANDROID_HOME` or `ANDROID_SDK_ROOT` to the SDK directory.

Accept Google’s SDK terms using its installer, then install the pinned components:

```sh
sdkmanager 'platforms;android-36' 'build-tools;36.0.0'
npm ci --ignore-scripts --no-audit --no-fund
```

Build scripts are cross-platform Python/Node, with Android tool suffixes selected per host. Linux is the currently verified build host; Windows/macOS build execution still needs native verification. On Windows use `py -3` for Python commands.

## Checks and development

```sh
python3 -m unittest discover -s tests -v
npx playwright install chromium
npm run build:web
npm run test:web
python3 scripts/build.py --debug
```

`CHROMIUM_PATH` may select an existing Chromium binary for browser acceptance. The tests exercise remote navigation, hold-OK, twelve favourites, large app libraries, theme and motion preferences, international dates and scaled viewports.

The debug APK is `dist/mare-launcher-debug.apk`. A local development key is created under ignored `.build/`; WebView inspection is enabled. It is not an installable public release and normally cannot upgrade a production-signed installation. Use an emulator or dedicated development TV.

To install on an explicitly selected test device:

```sh
python3 install.py --serial emulator-5560 --apk dist/mare-launcher-debug.apk
```

The ordinary installer’s verification and recovery rules apply. Add `--replace-stock-home` only when needed and appropriate on that test device. With the debug build running as Home, `MARE_TEST_TARGET=emulator-5560 node tests/android.cjs` checks the native bridge, remote buttons, app launching and Settings. Set `ADB` if the executable is not on PATH. This optional check temporarily changes favourites and Motion and restores them on completion. It does not run automatically against a discovered TV.

## Production build

Commit the reviewed source first, and use a clean working tree. Run the build in an environment without release credentials:

```sh
python3 scripts/build.py
python3 scripts/check_apk.py
```

This creates `dist/mare-launcher-unsigned.apk`, `dist/release.json` and `dist/SHA256SUMS`. The checker inspects the binary manifest, exact permission set, fonts, licences, APK digest and source hashes. Provenance records the source revision and whether the tree was dirty. Versions and SDK levels are managed in root `release.json`; keep `package.json` and its lockfile version aligned.

Dependencies are pinned, but byte-for-byte reproducibility of APK ZIP timestamps has not been established. Use the recorded digest to identify the exact candidate. A rebuild can produce a different digest.

## Separate local signing

Production APKs are signed locally and published through GitHub Releases. Do not upload a keystore or password to Actions. Keep the release signing identity backed up privately: Android updates depend on retaining it. The 0.3.0 release retains the signing identity used by the existing Maré previews.

Use a trusted copy of the signing helper and Android SDK in a signing environment that does not execute contributor build code. Transfer the reviewed unsigned APK with its matching `release.json`; independently record the approved unsigned SHA-256. Set `MARE_KEYSTORE_PASSWORD` privately in that environment, then run:

```sh
python3 scripts/sign.py --apk dist/mare-launcher-unsigned.apk --expected-sha256 APPROVED_UNSIGNED_SHA256 --keystore /private/path/mare-launcher.jks --key-alias mare-launcher
```

Unset the password afterwards. The helper produces `dist/mare-launcher.apk`, verifies its signature and updates the adjacent metadata and checksum. It does not run a build or upload anything. `--build-tools` chooses the trusted installed signer version; `--password-env` can name a different password variable.

Bring the signed artifact back to the clean reviewed checkout and inspect/package it:

```sh
python3 scripts/check_apk.py
python3 scripts/package_release.py
```

The `dist/mare-launcher-install.zip` bundle contains the signed production APK, guided installer, platform-tool pins, installation/compatibility guides, notices and checksums. Contributor documentation stays in the source repository. It excludes source workspaces, keys, device evidence and CI credentials. Packaging rejects unsigned/debug APKs and builds from dirty or uncommitted trees. Output stays in ignored `dist/`; no tool in this repository publishes a release.

Before publication, verify the ZIP’s contents and checksum, install it from a fresh extraction, verify Home after a normal reboot, and restore the previous Home from the saved record. Record the exact tested revision, OS and TV/WebView versions. Native macOS/Windows installation and additional manufacturers remain separate compatibility gates.
