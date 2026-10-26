# Release scope

PaperDesk 0.3.1 provides a Windows x64 installer and a source distribution. The installer includes Electron 44.9.3, Python 3.12.10, and the official native Codex CLI 0.162.1. Python or Node.js need not be installed on the user's machine. Windows 11 x64 is the validated host.

EPUB 2/3 is supported through generated reading pages; see [Document formats](FORMATS.md). Automatic update downloads remain disabled.

## Build the installer

Maintainers need Windows x64, the source environment created by Setup-PaperDesk.cmd, and Node.js 24. Run `Build-PaperDesk.cmd` or `scripts/build_desktop.ps1`. Build tools use requirements-build-hashed.txt and package-lock.json. npm installation scripts are disabled; known npm advisories fail the build gate. The pinned native CLI is reinstalled from the official registry before staging.

The pipeline stages only official CLI program files, builds a folder-based Python backend to avoid repeated extraction during document processing, then creates an NSIS installer. Unused voice libraries are omitted. Runtime license notices are included.

Outputs are in `dist/electron/`. Publish the `PaperDesk-Setup-0.3.1.exe` and its SHA-256 checksum through GitHub Release Assets. `win-unpacked/` is a complete app directory for validation, not a single-file portable executable. The installer is unsigned; no signing credentials are configured.

## Validate before publication

Run Python/JavaScript regressions and the optional `node scripts/verify_desktop.cjs` check. That script launches the actual packaged app with an isolated data/profile directory and removes Python/Node.js from the application PATH. It checks CLI detection, sign-in UI, PDF/EPUB, notes, exports, authenticated source documents and backend shutdown. Configure Playwright and the test Python overrides in the script header. These are maintainer test tools, not end-user dependencies.

Also test installation into a path containing spaces, reinstallation, and removal. Preserve any existing installation; use a clean account or isolated test machine for installer lifecycle checks. Notes and documents must remain outside the program directory. Cross-version upgrades and other Windows installations require additional validation; PATH isolation on the development host is not a fresh-OS VM test.

Commit and push the exact reviewed source before creating a release tag. Assets built from an uncommitted tree should be matched against the published source or rebuilt from the clean commit. Keep personal data and build output out of Git.

## Source package

```powershell
.\.venv\Scripts\python.exe scripts/prepare_source_release.py --check-only
.\.venv\Scripts\python.exe scripts/prepare_source_release.py
```

The source ZIP, RELEASE-MANIFEST.json, and SHA256SUMS.txt are in `outputs/`. Packaging excludes private directories, documents, credentials, installed dependencies and diagnostics. Source users still need Python and Node.js; a source ZIP is not the installer.

## Data and authentication

The installer defaults to `%USERPROFILE%\PaperDesk` for library/configuration and `%APPDATA%\PaperDesk` for window/cache state. Source mode uses the checkout's data/. Reinstallation and uninstallation preserve data. Existing library paths can be selected in settings; no automatic source-library migration occurs.

Official CLI authentication remains in the user's Codex profile or credential store. Login requires an explicit click and runs the official browser flow. Existing valid credentials can be reused. PaperDesk's local HTTP session remains separate. Original PDF windows share only the local Electron session and have no Node integration or application preload; EPUB downloads use the authenticated session. External links receive no local authentication token.

See [validation](VALIDATION.md), [data flows](../CONNECTIONS.md), and [project origin](../PROVENANCE.md).
