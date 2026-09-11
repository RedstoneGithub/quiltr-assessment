## Requirements and setup

- Python 3.10+

Run all commands below from the repository root. First create a virtual
environment:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in Windows PowerShell or
`source .venv/bin/activate` on macOS/Linux. Then install every task's
dependencies:

```bash
python -m pip install -r task1/requirements.txt \
  -r task2/requirements.txt \
  -r task3/requirements.txt \
  -r task4/requirements.txt
```

Copy `.env.example` to `.env` and replace its placeholder credentials before
making live LLM requests. The `.env` file is ignored by Git and must not be
committed.

## Configuration

| Variable | Used by | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Tasks 3 and 4 | Task 3 provider key and Task 4 primary-key fallback |
| `PRIMARY_API_KEY` | Task 4 | Optional override for the primary provider key |
| `BACKUP_API_KEY` | Task 4 | Backup provider key; required for live failover |
| `PRIMARY_LLM_URL` | Tasks 3 and 4 | OpenAI-compatible base URL; defaults to `https://openrouter.ai/api/v1` |
| `BACKUP_LLM_URL` | Task 4 | Backup base URL; defaults to `https://api.openai.com/v1` |
| `PRIMARY_MODEL` | Tasks 3 and 4 | Primary model slug |
| `BACKUP_MODEL` | Task 4 | Backup model slug |
| `RATE_LIMIT_DATABASE` | Task 4 | SQLite database path |
| `DOWNSTREAM_MCP_URL` | Task 2 | Downstream MCP endpoint |

Task 4 accepts provider URLs either as a base URL or with
`/chat/completions` already appended.

## Task 1: strict MCP server

```bash
python task1/server.py
```

The server uses stdio transport. Standard output is reserved for MCP JSON-RPC
messages, while validation failures use JSON-RPC error code `-32602`.

## Task 2: MCP security gateway

Start the downstream mock MCP server and the gateway in separate terminals:

```bash
python task2/mcp_server.py
```

```bash
python -m uvicorn task2.main:app --port 8001
```

The gateway listens at `http://127.0.0.1:8001/mcp`. The downstream server
defaults to `http://127.0.0.1:8002/mcp`. Use `Authorization: Bearer admin` for
admin tools or `Authorization: Bearer viewer` for non-admin access.

## Task 3: streaming PII guardrail

```bash
python -m uvicorn task3.main:app --port 8003
```

Example request:

```bash
curl -N -X POST "http://127.0.0.1:8003/generate?request=Hello"
```

The endpoint streams plain text while redacting email addresses, SSNs, and
credit-card-like values, including values split across provider chunks.

## Task 4: rate limiting and model fallback

```bash
python -m uvicorn task4.main:app --port 8004
```

Example request:

```bash
curl -X POST \
  "http://127.0.0.1:8004/generate?msg=Hello&max_tokens=100" \
  -H "X-API-Key: tenant-test-key"
```