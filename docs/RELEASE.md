# Release scope

PaperDesk 0.1.0 is a Windows x64 source distribution using a local Python service and a browser interface. Python 3.12 and Node.js 24 are recommended.

## Source package

Run from an installed project:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_source_release.py --check-only
.\.venv\Scripts\python.exe scripts/prepare_source_release.py
```

The `outputs/` directory contains:

- `paperdesk-0.1.0-source.zip`
- `RELEASE-MANIFEST.json`: per-file SHA-256 hashes.
- `SHA256SUMS.txt`: the ZIP checksum.

The packaging tool checks private paths, potential credentials, and dependency sources. Personal documents, authentication data, installed dependencies, and diagnostic logs are excluded.

## Support and limitations

- Executable installers, signing, and other operating systems are not part of the current release.
- Source setup does not install the Electron build toolchain. Its 2026-10-11 audit reported eight moderate advisories; reassess these before preparing a desktop installer.
- PDF workers limit concurrency, elapsed time, CPU, and memory. Model processes restrict unnecessary tools. They operate under the current OS user rather than a separate low-privilege account.
- Online metadata lookup for local papers is disabled by default. Authors and publication years may need manual entry.
- Back up personal data before updating and rerun Setup after obtaining new source. Automatic update downloads are not provided.

See [validation](VALIDATION.md), [data flows](../CONNECTIONS.md), and [project origin](../PROVENANCE.md).
