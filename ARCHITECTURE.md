# Architecture

PaperDesk consists of a local Python HTTP service and a browser interface. The frontend uses HTML, CSS, and JavaScript without a build step. Node.js runs the official Codex CLI. The Python package name remains `easyread` for compatibility.

```mermaid
flowchart LR
  Browser[Browser workspace] -->|Authenticated local HTTP| Server[Python service]
  Server --> Library[Local library and preferences]
  Server --> PDF[Resource-limited PDF workers]
  Server --> CLI[Codex CLI]
  CLI --> Model[Configured model provider]
  Server --> API[Custom model API]
  Library -. Optional sync folder .-> Sync[External sync client]
```

## Components

| Module | Responsibility |
|---|---|
| `easyread/server.py`, `library_api.py` | Local HTTP endpoints, authentication, and library operations |
| `easyread/library.py`, `store.py` | Document storage, annotations, and operation merging |
| `easyread/engines.py`, `chat.py` | Model requests, streaming, usage reporting, and cancellation |
| `easyread/account_usage.py`, `usage.py`, `budget.py` | Account quotas and local usage limits |
| `easyread/pdf_isolation.py`, `pdfwork.py` | PDF processing, resource limits, and page images |
| `easyread/cloudlib*.py` | Library copy, switch, merge, and rollback |
| `easyread/web/` | Library, reading workspace, and shared settings |

## Design decisions

- The current distribution targets Windows x64 and runs from source.
- Documents and preferences are stored locally. Cloud synchronization is handled by a user-selected sync client.
- The Codex CLI manages model authentication and retains its configured provider and proxy settings.
- PDF workers have resource limits; model processes restrict unnecessary tools. Both run under the current operating-system user.
- Changes to storage and shared reading flows must preserve existing data and cover cancellation, recovery, and compatibility.

See [data flows](CONNECTIONS.md), [validation](docs/VALIDATION.md), and [release scope](docs/RELEASE.md).
