# Contributing

Keep one launcher and one APK for every supported TV. Device preferences such as favourites and Motion should stay preferences. Preserve the existing Maré geometry, sand, fonts, English interface, day–month dates and 24-hour time unless an intentional design change is agreed.

Follow [BUILDING.md](docs/BUILDING.md) for local setup and checks. Include the problem, resulting behaviour and relevant validation with a change. For device-specific behaviour, report manufacturer/model, Android version and WebView version, plus whether it was an emulator or physical TV. Keep private identifiers, addresses, account information and full device dumps out of issues and commits.

Installer changes need fault/recovery tests. A failure must not leave the user guessing which Home packages to re-enable. Keep manufacturer restrictions explicit and reversible; never add automatic broad debloating, unlocking or factory resets.

CI changes require careful review of [CI_SECURITY.md](docs/CI_SECURITY.md). Tests and dependency install/build scripts are executable contributor code too. Do not add secrets, self-hosted runners, privileged PR execution or release automation.

Contributions must be compatible with the project’s MIT licence and preserve third-party notices. Public repository contribution and security-reporting links will be added when publication is approved.

All files are owned by the Maré Rio `launcher-maintainers` team. Member-owned PRs satisfy ownership; other PRs require that team’s approval. CI is required for everyone, with no ruleset bypass actors.
