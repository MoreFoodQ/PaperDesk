# Third-party notices

PaperDesk retains the upstream EasyRead MIT copyright in `EasyRead-MIT.txt` and the root LICENSE.
KaTeX assets and fonts use `KaTeX-MIT.txt`. Python dependency license texts are retained in their respective directories; versions are pinned in requirements-lock.txt.

The Windows installer includes Python 3.12 and PyInstaller's unmodified bootloader. See Python-3.12-LICENSE.txt and PyInstaller-COPYING.txt, including the bootloader distribution exception. Build-tool notices are retained under build-tools/.

Official Codex CLI 0.162.1 is distributed with unmodified native executables required for text/image use, code-mode support and Windows sandbox helpers. Its source is https://github.com/openai/codex/tree/rust-v0.162.1 and its license is Codex-Apache-2.0.txt. Publisher NOTICE, when supplied, is retained as Codex-NOTICE.txt. Unused native voice components are omitted; PaperDesk disables realtime conversation. Ripgrep's license is ripgrep-MIT.txt. Account credentials are not part of the runtime distribution.

The Electron distribution supplies LICENSE.electron.txt and LICENSES.chromium.html in the installed application directory. App code uses only Electron and Node.js built-ins; electron-updater is not bundled. Build-only npm packages are listed in npm-dependencies.json and npm-sbom.cdx.json.

Certifi's CA data uses MPL 2.0. Corresponding source: https://github.com/certifi/python-certifi at the version pinned in requirements-lock.txt. License: https://www.mozilla.org/en-US/MPL/2.0/ . PDFium notices are retained with pypdfium2.

The installer includes no sample papers, user documents, authentication files, or local settings. Palette references are Nord, Catppuccin Mocha, and Dracula; their code, fonts and artwork are not bundled.
