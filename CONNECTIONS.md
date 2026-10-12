# Network connections and data flows

PaperDesk stores its library locally. Network activity depends on the operation and the selected model provider.

## Connections

| Operation | Destination | Data exchanged |
|---|---|---|
| Initial setup | PyPI and `registry.npmjs.org` | Pinned Python wheels and the official Codex CLI package. Downloads are checked against hashes or package integrity metadata. |
| Local PDF import without AI | Local PDF workers | PDF parsing, page images, and extracted text remain local. Online metadata lookup is disabled by default. |
| Optional metadata lookup | arXiv and Semantic Scholar | Recognized arXiv identifiers or DOIs, rather than the complete PDF. |
| URL, identifier, or title import | Public document hosts and metadata services | Queries and downloads needed to locate a paper. Download validation rejects local files, private addresses, and redirects to non-public IPs. |
| Translation, text organization, or questions | Configured CLI or API provider | Relevant document text, conversation context, and optional page images. |
| Account quota lookup | Official Codex account service | A read-only quota request through `app-server`; no paper content or model turn. |
| Tool detection | Local CLI processes and optional local model endpoints | Version and availability checks; no paper content. |
| Optional cloud synchronization | User-selected sync provider | Files in the selected sync folder, uploaded by the external sync client. |

The default installation does not install the Electron build toolchain. PaperDesk currently has no automatic update download service.

## Provider configuration

Codex requests use the CLI's active authentication, provider, and proxy configuration. Custom API requests use the endpoint selected in model settings. Review those settings before processing confidential documents.

Model usage and costs depend on the selected provider and account. Quota lookup is a shared-account snapshot, not a per-model balance.

## Credentials and sharing

Each user supplies their own model authentication. Project data, API keys, CLI credentials, and authenticated local launch URLs should remain private. Access logs omit URL query strings.

Pinned versions and integrity checks verify the downloaded package source and contents. Runtime dependencies remain third-party software. See [SECURITY.md](SECURITY.md) for the supported security scope and reporting process.
