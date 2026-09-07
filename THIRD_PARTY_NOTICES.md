# Licences and provenance

The root MIT licence covers Maré Launcher and the Maré-owned source, styling, icons, mark and material copies distributed in this repository, authorised by their copyright holder for this launcher’s open-source distribution. It does not change the licence of the separate `mare-rio/mare-design-system` repository, whose upstream licence is reserved.

| Included material | Licence | Notice |
| --- | --- | --- |
| React 18.3.1 | MIT | `licenses/LICENSE-react.txt` |
| React DOM 18.3.1 | MIT | `licenses/LICENSE-react-dom.txt` |
| Scheduler 0.23.2 | MIT | `licenses/LICENSE-scheduler.txt` |
| Fraunces, roman and italic variable fonts | SIL Open Font License 1.1 | `licenses/LICENSE-fraunces.txt` |
| Inter variable font | SIL Open Font License 1.1 | `licenses/LICENSE-inter.txt` |
| Geist Mono variable font | SIL Open Font License 1.1 | `licenses/LICENSE-geist-mono.txt` |

Font notices and reserved-name conditions remain in force. Fonts are redistributed unchanged. React, React DOM and Scheduler are bundled into the generated browser runtime. Dependency development-tool licences remain available in their npm packages; those tools are not distributed inside the Android APK.

`vendor/mare/provenance.json` records the design-system source revision and the SHA-256 of the copied component/style/font/material files. These are included so public builds do not need a private checkout. The original Maré sand texture and horizon are preserved. `dist/release.json` records hashes of the files used for each local build.

Google Platform Tools are not included in this repository, APK or installation ZIP. The installer optionally obtains pinned archives directly from Google after separate acceptance of Google’s SDK licence. See `scripts/platform-tools.json` for URLs and integrity pins. No streaming-app APKs are redistributed.

App names and wordmarks displayed for installed third-party apps identify those apps; they do not imply endorsement. The documentation’s browser screenshots use demonstration app entries and are not captures of a user’s TV or account.
