# Maré Launcher

- Maintain one launcher and one build for all TVs. Device preferences are not separate implementations.
- Preserve the Maré grid, fonts, sand, English and international date/time conventions.
- Use standard Android TV APIs. Keep manufacturer-specific recovery choices in the installer, explicitly selected and reversible.
- The installer must verify its target, save original state before mutations, preserve data on upgrades and recover safely from interruption.
- Run installer tests, browser acceptance and a production Android build for relevant changes. Record the limits of hardware validation.
- Public CI runs without secrets on GitHub-hosted runners, with a read-only token and pinned actions. Signing is a separate local step. Do not add release automation or privileged PR triggers.
- Never commit device evidence, IP addresses, private signing keys or private workspace files.
