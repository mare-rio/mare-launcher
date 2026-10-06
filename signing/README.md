# The signing key is public

Android installs only signed APKs, and replaces an installed app only with one signed by the same
key. Maré Launcher is installed over ADB from a computer on the TV's own network, so a private key
would protect nothing an attacker could not already do there. `mare-launcher.p12` is therefore
committed on purpose: every build of a commit, on any machine or in CI, produces the same
installable launcher, and the key cannot be lost again.

- Keystore: PKCS #12, alias `mare-launcher`, password `mare-launcher`.
- Certificate: `CN=Mare Launcher`, SHA-256
  `06:FB:78:85:2A:9B:22:57:69:62:9B:A9:4C:E8:49:98:93:89:4E:EB:67:98:C2:F7:2E:50:4E:53:E8:EB:C8:B7`.

Releases up to 0.3.3 were signed with an earlier private key (`CN=Mare TV local preview`), lost with
the maintainer's data in 2026. From 0.4.0 on, a TV running an earlier release reinstalls once: run the installer's
**Restore my previous Home screen** with removal, then install (docs/INSTALLATION.md).
