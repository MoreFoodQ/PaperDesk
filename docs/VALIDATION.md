# Validation

Scope: the Windows x64 source distribution and local browser interface.

## Results

| Check | Result |
|---|---|
| Python regressions | 344 passed on 2026-10-11; 346 after thumbnail-cache tests were added on 2026-10-12 |
| JavaScript regressions | 109 passed |
| Clean Python 3.12 environment | The 344-test baseline and PDF smoke checks passed on 2026-10-11; 13 PDF-related tests passed on 2026-10-12 |
| Browser workflows | PDF import and source pages, note saving and reload, offline export, trash restore, search, languages, palettes, and desktop/mobile layout checks passed |
| Official CLI integration | Synthetic translation, questions, and read-only account quota lookup passed |

Unit and smoke tests use synthetic fixtures. Commands are listed in the [English README](../README.en.md#development) and [Traditional Chinese README](../README.md#開發).

## Coverage limits

External model APIs are exercised with simulated HTTP responses. Live third-party accounts, local model inference, cross-device cloud synchronization, other operating systems, and executable installers are outside the current validation scope.

GitHub Actions results must be checked after pushing. Local results do not establish remote CI status.

## Thumbnail cache regression

On 2026-10-12, a race between background thumbnail generation and HTTP reads was reproduced. Cache generation now uses process-local synchronization and atomic publication of completed files. Empty cache files are regenerated.

Concurrent publication and empty-cache regressions, the full Python suite, and PDF/export smoke checks passed. README screenshots use three original synthetic documents and notes; capture does not require live model calls.
