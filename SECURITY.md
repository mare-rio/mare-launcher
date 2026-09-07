# Security

Maré loads its bundled interface from a fixed local asset origin. It does not request Android’s `INTERNET` permission, load remote pages, collect analytics or contain account credentials. Its WebView bridge accepts installed-app and TV-input identifiers from the current Android catalog. Production builds disable WebView inspection. Network-state access is used only to show connection status.

The network ADB installer changes the active profile’s launcher selection and, only with explicit fallback selection, supported Google Home package states. Keep its recovery record. Enable debugging only on a trusted network and turn it off after installation.

The initial candidate is unpublished. Before publication, reports should go directly to the project owner through an established private contact. Once a public repository exists and private vulnerability reporting is enabled, use its **Security → Report a vulnerability** form. Do not post credentials, pairing codes, private device inventories or signing material in a public issue.

Describe the affected revision, Android/WebView versions, reproduction steps and impact. Redact device identifiers and addresses. For CI risks, see the [contributor trust and CI design](docs/CI_SECURITY.md).
