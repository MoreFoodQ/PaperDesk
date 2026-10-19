# Validation

Scope: the Windows x64 source distribution and local browser interface.

## Results

| Check | Result |
|---|---|
| Python regressions | 361 passed on 2026-10-13 after Windows packaging regressions; EPUB baseline: 357 passed on 2026-10-12 |
| JavaScript regressions | 116 passed on 2026-10-13; baseline: 109 passed |
| Clean Python 3.12 environment | The 344-test baseline and PDF smoke checks passed on 2026-10-11; 13 PDF-related tests passed on 2026-10-12; all 19 EPUB/i18n tests passed for 0.2.0 on Python 3.12 |
| Browser workflows | PDF import and source pages, note saving and reload, offline export, trash restore, search, languages, palettes, and desktop/mobile layout checks passed |
| Official CLI integration | Synthetic translation, questions, and read-only account quota lookup passed |

Unit and smoke tests use synthetic fixtures. Commands are listed in the [English README](../README.en.md#development) and [Traditional Chinese README](../README.md#開發).

## Coverage limits

External model APIs are exercised with simulated HTTP responses. Live third-party accounts, local model inference, cross-device cloud synchronization and other operating systems are outside the current validation scope. Windows installer evidence and its remaining limits are documented below.

GitHub Actions results must be checked after pushing. Local results do not establish remote CI status.

## Thumbnail cache regression

On 2026-10-12, a race between background thumbnail generation and HTTP reads was reproduced. Cache generation now uses process-local synchronization and atomic publication of completed files. Empty cache files are regenerated.

Concurrent publication and empty-cache regressions, the full Python suite, and PDF/export smoke checks passed. README screenshots use three original synthetic documents and notes; capture does not require live model calls.

## Reader drawer regression

On 2026-10-12, the closed drawer retained part of its width because its transform did not include the navigation offset. The drawer now leaves the viewport completely, disables interaction while closed, and keeps the header and navigation controls outside the overlay.

The optional `scripts/verify_reader_drawer.cjs` browser regression checks repeated header and dock toggles, the T shortcut, overlay dismissal, focus exclusion, and horizontal overflow at 390, 600, 899, 900, 980, 1180, 1359, 1360, and 1600 pixels. All widths passed. JavaScript regressions (109), i18n/release checks (14), and PDF/export smoke checks passed. Browser runtime overrides are documented in the script header.

## EPUB 0.2.0 integration

| Problem | Change | Result |
|---|---|---|
| EPUB uses chapter order rather than fixed PDF pages | Validate container/package/spine and produce bounded reading pages; retain the original EPUB | EPUB 2/3, Traditional Chinese, chapter order, basic tables and embedded images passed |
| Format-specific content could bypass existing protections | Isolated worker, archive/path/entity/encryption limits, no publisher scripts or external image loading | Hostile archive/XML tests and no-external-request browser checks passed |
| Generated PDF bytes are not the original book identity | Hash `source.epub` for import and migration verification | Duplicate import retained notes; original digest and download bytes matched |
| Translation may assume English or original pagination | EPUB-only language/page context; PDF prompts unchanged | Text and vision model paths, original-only mode, cancellation, and note preservation passed with model substitutes |
| Changes could affect existing reader operations | Shared reader/storage/export flow with format-specific labels | Mixed PDF/EPUB import, page images, authenticated original download, note save/reload, and offline HTML rendering passed in the browser |
| Public source should exclude personal books | Ignore PDF/EPUB files and exclude them from source packaging | No source documents included in Git's tracked file set |

Python regressions: 357 passed. JavaScript regressions: 109 passed. The existing drawer regression passed at all nine viewport widths. PDF CLI import, authenticated reader, source image, and offline export smoke checks passed. The 19 EPUB/i18n tests also passed in the clean Python 3.12 environment.

EPUB model tests simulate responses while exercising actual image preparation, prompt assembly, block merging, character positioning, and note storage. No new live model calls were made for this release. The existing official CLI integration remains the same; live EPUB translation quality and publisher-specific books are not established by these checks. Test fixtures are generated in temporary directories and contain no personal literature.

## Windows installer validation (2026-10-13)

| Problem | Change | Result |
|---|---|---|
| Source users needed Python and Node.js | Bundle Electron, a folder-based Python 3.12 backend and pinned native Codex 0.162.1 | Actual packaged and installed app passed with Python/Node removed from application PATH |
| Frozen document imports needed a profile/data location | Give isolated workers a private home path and the selected UI language; exclude account credentials | Frozen-environment regression and real PDF/EPUB preparation passed |
| External browsers lack the desktop authentication cookie | Open local PDFs in sandboxed session-sharing windows; use authenticated EPUB downloads | Popup policy regressions and real original PDF windows passed |
| New users need CLI authentication | Explicit trusted IPC launches the official browser login; no credential data is staged | Untrusted sender, process concurrency, failure/quit cleanup, and native login UI checks passed; existing ChatGPT login was reused for the model smoke |
| Build dependencies had eight moderate npm advisories | Remove unused updater runtime and override the official download dependency with @electron/get 5.1.0 | npm audit: 0 known advisories at the validation date |
| Packaging must exclude personal data | Fixed runtime/file allowlists, original native hashes, preserved runtime notices | Packaged-content and source privacy gates passed |
| Installation lifecycle could affect notes | Per-user installer, reading data outside program files, preserve data on uninstall | Path with spaces, reinstall and uninstall passed; synthetic note hashes unchanged and test uninstall entry removed |

Full Python suite: 361 passed. JavaScript suite: 116 passed. Packaged browser checks included PDF/EPUB import, source images, note save/reload, source download authentication, local PDF windows, offline HTML and backend shutdown. Those checks used an isolated synthetic library and no model calls.

One separate installed-app smoke used gpt-5.6-luna, low reasoning and standard service tier, returning a short JSON object through the bundled CLI. Local usage accounting recorded one call and 8,184 reported tokens, including CLI context. No live translation of user literature was performed. Fresh-account interactive OAuth, cross-version upgrades, a fresh-OS VM, other operating systems and code signing are not established by these tests. The installer is unsigned.

## Optional figure text translation (2026-10-19)

Feature branch: `feat/optional-figure-translation`. Full Python regression baseline:
385 passed; JavaScript: 118 passed. Feature checks cover default/legacy behavior,
boolean API validation, task snapshots, confirmation, resume, original-mode fills,
explicit image fills, missing replies, retries, cancellation, mixed task batches,
explicit full-page retranslation versus image-only retry semantics, and preservation
of source images, body blocks, notes, captions and review entries.
The isolated browser check passed setting save/reload, PDF/EPUB skip/fill workflows,
exports and reader widths 390, 900 and 1440. No live model calls were made.
See [behavior, issue/change/result records and release handling](FIGURE-TRANSLATION.md).

The final source import/authentication/export smoke and release privacy gate passed.
The existing reader drawer regression passed at all nine supported test widths.
Remote CI and rebuilt installer validation are pending publication of the branch.

## GitHub Actions workflow correction (2026-10-19)

The first feature-branch push (81de0d2) produced a failed workflow with no jobs.
Review found runner.temp used in jobs.source.env, where the runner context is not
available. The isolated EASYREAD_HOME path is now set by a PowerShell step using
RUNNER_TEMP and GITHUB_ENV before tests. This changes CI setup only; the application
and its data paths are unchanged. Remote execution must be verified after pushing
this correction; local regression results do not imply that remote CI passed.

## Traditional Chinese developer documentation (2026-10-19)

Developer-facing Python docstrings and comments, JavaScript/CSS comments and issue
templates now use Traditional Chinese and Taiwan terminology. Existing reviewed
README prose, code examples, URLs, third-party notices and license text are retained.
Outdated explanations of data locations, service grouping, version checks and
browser lifetime handling were rewritten to match current behavior.

| Problem | Change | Result |
|---|---|---|
| Simplified Chinese in developer explanations | Convert only parsed comments/docstrings; review technical terms and ambiguous characters | Documentation-token scan found no remaining Simplified-only candidates |
| Bulk wording changes could affect execution | Compare Python and JavaScript syntax trees and strip-comment CSS/HTML representations | 129 Python and 87 JavaScript files parsed; application execution trees unchanged; 14 CSS and 2 HTML files retain executable content |
| Palette tests used a translated comment as a source delimiter | Locate the existing code declarations and validate the boundaries | All 118 JavaScript tests passed |
| Several explanations described older defaults | Correct data paths, optional updates and provider/network descriptions | Documentation matches current implementation without changing settings |

All 385 Python tests passed, along with the source startup/import/authentication/
export smoke and release privacy gate. The UI string check reported no missing
English entries or unwrapped interface strings. No live model calls were made.

Legacy localization keys, model prompts, regular expressions, stored-data labels
and test fixtures retain their original strings for compatibility. Their presence
does not mean they are newly added developer prose. Translating those values would
require separate compatibility and behavior changes. Runtime dependencies, package
versions, personal libraries and existing installer binaries were not changed.
The JavaScript tree comparison has one reviewed test-only exception: the palette
test's source delimiter was replaced with code declarations rather than comment text.
