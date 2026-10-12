# Contributing

Bug reports, documentation improvements, and focused pull requests are welcome. Follow the [README](README.en.md#quick-start) to set up a development environment.

## Reporting issues

Include the version, reproduction steps, expected behavior, and actual behavior. Use a synthetic document when possible and remove credentials, authenticated URLs, and personal information from attachments.

Security reports follow [SECURITY.md](SECURITY.md).

## Pull requests

1. Create a branch from `main`.
2. Keep the change focused on a specific issue or feature.
3. Run the relevant tests and the source-release check described in the README.
4. For storage, model, or library changes, verify saving, cancellation, recovery, and existing-data compatibility.
5. Describe the behavior changed, validation performed, and any remaining limitations.

Add regression tests for new behavior or reproducible bugs. Documentation-only changes can be validated with link and content checks.

## Test data and repository hygiene

Use synthetic fixtures. Live model tests are optional; choose a small model and short inputs, and record the calls and reported usage.

Keep personal PDFs, `data/`, credentials, `.env` files, installed dependencies, and local diagnostic logs out of commits. Inspect `git diff --cached` before submitting a change.

```powershell
.\.venv\Scripts\python.exe scripts/prepare_source_release.py --check-only
```
