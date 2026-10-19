# PaperDesk

[繁體中文](README.md) | **English**

![Python](https://img.shields.io/badge/Python-3.10%E2%80%933.13-3776AB?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-20%2B-5FA04E?logo=nodedotjs&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-Vanilla-F7DF1E?logo=javascript&logoColor=black)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-663399?logo=css&logoColor=white)

A paper-reading workspace with bilingual PDF and EPUB reading, translation, GPT assistance, notes, and library management.

PaperDesk runs locally and opens in your browser. It uses the official Codex CLI by default to connect to models. Windows x64 installer and source distributions are available.

[Quick start](#quick-start) · [User guide](docs/USAGE.md) · [Architecture](ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md)

## Features

- **Paper library**: Import local PDFs, EPUB books, or public paper URLs, search and categorize papers, view details, and restore deleted items from the trash.
- **Bilingual reading**: Switch between the original, translation, and bilingual views. Navigate outlines and terminology while comparing passages with the source PDF.
- **Figure text translation**: enabled by default. Turn it off under Settings → Models while retaining body and caption translation. Skipped labels can be translated later without retranslating the body. [Behavior and validation](docs/FIGURE-TRANSLATION.md)
- **GPT reading assistant**: Use relevant passages and optional page images for translation, questions, and help with notes.
- **Notes and export**: Text annotations, paper-level notes, automatic saving, Markdown export, and self-contained HTML for offline reading.
- **Models and usage**: Codex CLI, Claude Code, local model services, and custom APIs; official account quota lookup and local daily usage limits.
- **Reading preferences**: Traditional Chinese and English interfaces, fonts, text size, line spacing, keyboard shortcuts, and five dark palettes.

## Screenshots

These screenshots use synthetic demonstration documents and notes. The interface shown is Traditional Chinese; English is also available in settings.

### Reading workspace

Bilingual passages, the paper outline, and the original PDF side by side.

![Reading workspace with bilingual passages and the original PDF](img/reading-workspace.png)

<details>
<summary>Library, notes, and reading settings</summary>

### Library

![Paper library with categories, search, and paper details](img/library.png)

### Paper notes

![Paper notes with reading highlights and follow-up questions](img/notes.png)

### Reading settings

![Reading settings with dark palettes and language options](img/reading-settings.png)

</details>

## Quick start

### Windows installer

Download `PaperDesk-Setup-0.2.0.exe` from the Assets section of [GitHub Releases](https://github.com/MoreFoodQ/PaperDesk/releases). Install and open PaperDesk. Python and the official native Codex CLI are bundled; no separate Python, Node.js, or npm installation is required.

Choose **Do nothing yet** when importing documents for local reading. For translation or GPT questions, open **Settings → Models → Sign in to ChatGPT / Codex** and complete the official browser sign-in. An existing valid Codex login can be reused.

This build is unsigned. Compare the file with the Release's `SHA256SUMS.txt`; Windows may display an unknown-publisher prompt.

### Run from source

The following prerequisites apply to source execution and development.

### Requirements

| Component | Requirement |
|---|---|
| Operating system | Windows x64 |
| Python | 64-bit Python 3.10–3.13; 3.12 recommended |
| Node.js | Version 20 or later, including npm; 24 recommended |
| Model account | Translation and questions require a valid Codex CLI login or another configured model service |

### Install

Clone this repository, or download and extract it using **Code → Download ZIP** on GitHub. Open PowerShell in the project folder and run:

```powershell
.\Setup-PaperDesk.cmd
```

You can also double-click `Setup-PaperDesk.cmd`. The installer creates a project-local Python environment and installs the official Codex CLI using pinned dependencies and integrity checks.

### Sign in to Codex

```powershell
node .tools/codex/node_modules/@openai/codex/bin/codex.js login
node .tools/codex/node_modules/@openai/codex/bin/codex.js login status
```

An existing valid CLI login can be reused. Reading local PDFs and writing notes do not require a model login.

> When you sign in to Codex CLI with a ChatGPT account, translation and questions use your Codex/agentic-work allowance. API-key authentication uses API billing. Signing in to the ChatGPT website and signing in to the CLI are separate processes.

### Launch

```powershell
.\Open-PaperDesk.cmd
```

The launcher starts the local service and opens your browser. The default address is `http://127.0.0.1:8876`. If that port is in use, use the address opened by the launcher. Use the same launcher for subsequent sessions.

## Document formats

PDF and DRM-free, reflowable EPUB 2/3 are supported. EPUB chapters are repaginated for the existing reading, translation, GPT, notes, and offline HTML workflows. The original EPUB is preserved and available for download. Reading page numbers are generated locally and should not be cited as the original book's page numbers.

Publisher scripts are not executed and external images are not fetched. CSS is replaced with a common reading layout. Fixed-layout EPUB, SVG, MathML, media, DRM, and obfuscated fonts are currently unsupported. Limits: 32 MiB archive, 64 MiB expanded content, and 200 reading pages. See [Document formats](docs/FORMATS.md) for details.

## Usage

1. Import a PDF or EPUB. Choose “Do nothing yet” to view pages without a model; “Read the original” uses a model to organize content. Translation can be limited to selected pages.
2. Double-click a paper in the library to open the reading workspace.
3. Switch between original, translation, and bilingual views. Open the PDF panel to inspect the source pages.
4. Select text to add an annotation, or use the notes panel for paper-level notes.
5. Ask a question in the GPT panel, adding relevant passages or page images as needed.

Use **Settings → Models** to add models and custom APIs, **Settings → Quota & usage** to check official quotas or set local limits, and **Settings → Reading** to adjust typography, languages, and palettes.

Graphite Cyan is the default dark palette. Nord Mist, Mocha Lavender, Forest Mint, and Dracula Violet are also available.

See the [user guide](docs/USAGE.md) for additional operations, backups, and troubleshooting. The detailed user guide is currently available in Traditional Chinese.

## Data and privacy

Source execution stores documents, notes, conversations, and preferences in the project's `data/` directory. The installer defaults to `%USERPROFILE%\PaperDesk`, with window/cache state in `%APPDATA%\PaperDesk`. Reinstalling or uninstalling preserves reading data. Model authentication is managed by the official CLI.

- AI translation, organization, and questions send relevant text, conversation context, and optional page images to the selected model service.
- URL imports and online metadata lookups connect to external services. Metadata lookup for local papers is disabled by default.
- The library can use a local folder or a sync folder you select. Uploads are handled by your installed cloud-sync software.
- Wait for background tasks to finish and stop the service before backing up. Exclude personal data, API keys, and login credentials when sharing the project.

See [CONNECTIONS.md](CONNECTIONS.md) for data flows and security limits, and [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Development

The frontend is in `easyread/web/`, and the Python backend is in `easyread/`. The internal package name remains `easyread`.

After installation, run these commands from the project root:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
$files = (Get-ChildItem tests -Filter 'test_*.cjs').FullName
node --test $files
.\.venv\Scripts\python.exe scripts/verify_source.py
```

These tests use synthetic data and do not require live model calls. See [docs/VALIDATION.md](docs/VALIDATION.md) for coverage and results, and [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

To build a source release:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_source_release.py
```

The `outputs/` directory contains the source ZIP, a per-file manifest, and SHA-256 checksums. See [docs/RELEASE.md](docs/RELEASE.md) for supported platforms and known limitations.

## License and acknowledgments

PaperDesk is based on [EasyRead](https://github.com/Edwardxlai/easyread) and distributed under the [MIT License](LICENSE), with the upstream copyright notice preserved. See [PROVENANCE.md](PROVENANCE.md) for the source revision and main changes.

Third-party notices are in [licenses/](licenses/THIRD-PARTY-NOTICES.md). Imported papers and other documents remain subject to their own licenses.
