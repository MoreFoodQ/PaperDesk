# Security policy

## Supported scope

PaperDesk 0.1.0 is a Windows x64 source distribution intended for local use. The HTTP service binds to loopback and requires authentication. It is not intended to be exposed directly to the internet.

## Reporting a vulnerability

Use **Security → Report a vulnerability** when private vulnerability reporting is enabled for this repository.

If that option is unavailable, open an issue requesting a private contact channel without including exploit details or sensitive data. No separate security email is currently configured.

Include:

- The affected version and environment.
- Reproduction steps using synthetic data.
- The observed behavior and potential impact.
- A minimal example or proposed fix, if available.

Do not include API keys, login credentials, authenticated launch URLs, or private documents in public reports.

## Security boundaries

The application validates local HTTP requests, restricts download destinations, escapes untrusted output, and protects stored secrets with Windows DPAPI. PDF processing has resource and timeout limits, and model processes restrict unnecessary tools.

These processes run under the current Windows user. Operating-system account isolation is outside the application's scope. Provider configuration and external sync clients determine where model inputs and synchronized files are sent.

See [CONNECTIONS.md](CONNECTIONS.md) for data flows and [docs/RELEASE.md](docs/RELEASE.md) for release limitations.
