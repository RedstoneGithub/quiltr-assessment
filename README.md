# Requirements
- Python 3.10+

# How to Run
- For each task, cd into its directory and run pip install -r requirements.txt.
- Depending on the task, you may have to directly run a Python script, or run fastapi run/uvicorn main:app.

# Notes
- Configure `OPENAI_API_KEY` env variable for task3 and task4 to your preferred provider's API key (OpenAI compatbile endpoint)
- I have configured the LLM APIs for task3 and task4 to be OpenRouter's endpoint, but this is easily configurable using `PRIMARY_LLM_URL` env variable.
- Other configurable env variables are:
```text
BACKUP_LLM_URL
PRIMARY_MODEL
BACKUP_MODEL
RATE_LIMIT_DATABASE
```

## Task 1

```bash
python server.py
```

`server.py` uses stdio transport. Standard output is reserved for MCP JSON-RPC
messages.

## Task 2

Install the dependencies, then start the downstream server and gateway in
separate terminals:

```bash
python mcp_server.py
```

```bash
fastapi run --port 8001
```

Use `Authorization: Bearer admin` for admin tools and `Authorization: Bearer viewer` for viewer access. 
Set `DOWNSTREAM_MCP_URL` to override the default `http://127.0.0.1:8002/mcp` downstream URL.

## Task 3

```bash
fastapi run --port 8003
```

Example request:

```bash
curl -N -X POST "http://127.0.0.1:8003/generate?request=Hello"
```

## Task 4


```bash
uvicorn main:app --port 8004
```

Example request:

```bash
curl -X POST \
  "http://127.0.0.1:8004/generate?msg=Hello&max_tokens=100" \
  -H "X-API-Key: tenant-test-key"
```