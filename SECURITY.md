# Security

Maré loads its bundled interface from a fixed local asset origin. It does not request Android’s `INTERNET` permission, load remote pages, collect analytics or contain account credentials. Its WebView bridge accepts installed-app and TV-input identifiers from the current Android catalog. Production builds disable WebView inspection. Network-state access is used only to show connection status.

The network ADB installer changes the active profile’s launcher selection and, only with explicit fallback selection, supported Google Home package states. Keep its recovery record. Enable debugging only on a trusted network and turn it off after installation.

Report vulnerabilities through the repository’s private [Security → Report a vulnerability](https://github.com/mare-rio/mare-launcher/security/advisories/new) form. Do not post credentials, pairing codes, private device inventories or signing material in a public issue.

Describe the affected revision, Android/WebView versions, reproduction steps and impact. Redact device identifiers and addresses. For CI risks, see the [contributor trust and CI design](docs/CI_SECURITY.md).
