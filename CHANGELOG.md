# Changelog

## 0.3.0 — 7 September 2026

- Extract the existing Maré grid launcher into a standalone source package using only public dependencies and included design assets.
- Publish a downloadable signed APK and a guided installer ZIP with an offline walkthrough for TCL Android TV and Google TV owners.
- Add a setup menu for installation, updates, restoring Home and removal, with wireless pairing, integrity checks and a prompted Google Home fallback.
- Fit the same layout to different TV viewports, use standard Android input intents, and recover from a reclaimed WebView renderer.
- Disable WebView inspection in production and constrain the bundled page with a content security policy.
- Add local unsigned builds, separate signing and installation ZIP preparation, with unprivileged CI checks.

## 0.2.0 — private preview

The existing twelve-favourite Maré grid, clock, apps/inputs/settings panes and hold-OK controls, used on two Android 11 TCL TVs. Preserved as the basis of this package; there is no separate low-end launcher.
