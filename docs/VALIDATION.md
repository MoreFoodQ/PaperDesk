# Validation

Scope: the Windows x64 source distribution and local browser interface.

## Results

| Check | Result |
|---|---|
| Python regressions | 357 passed for 0.2.0 on 2026-10-12 (including 11 EPUB regressions) |
| JavaScript regressions | 109 passed |
| Clean Python 3.12 environment | The 344-test baseline and PDF smoke checks passed on 2026-10-11; 13 PDF-related tests passed on 2026-10-12; all 19 EPUB/i18n tests passed for 0.2.0 on Python 3.12 |
| Browser workflows | PDF import and source pages, note saving and reload, offline export, trash restore, search, languages, palettes, and desktop/mobile layout checks passed |
| Official CLI integration | Synthetic translation, questions, and read-only account quota lookup passed |

Unit and smoke tests use synthetic fixtures. Commands are listed in the [English README](../README.en.md#development) and [Traditional Chinese README](../README.md#開發).

## Coverage limits

External model APIs are exercised with simulated HTTP responses. Live third-party accounts, local model inference, cross-device cloud synchronization, other operating systems, and executable installers are outside the current validation scope.

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
