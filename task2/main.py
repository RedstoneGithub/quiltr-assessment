import json
import os
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

try:
    from .schema import Body
except ImportError:
    from schema import Body

downstream_server = os.getenv("DOWNSTREAM_MCP_URL", "http://127.0.0.1:8002/mcp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=10)
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan)


def create_json_rpc_error(
    requestId: Any, code: int, message: str, statusCode: int = 200
):
    return JSONResponse(
        status_code=statusCode,
        content={
            "jsonrpc": "2.0",
            "id": requestId,
            "error": {"code": code, "message": message},
        },
    )


def bearerRole(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    parts = authorization.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    role = parts[1].strip()
    if role not in {"admin", "viewer"}:
        return None
    return role


async def forward(payload: dict, body: Body, request: Request):
    req_headers = {}
    for header in ("accept", "mcp-session-id", "mcp-protocol-version", "last-event-id"):
        if header in request.headers:
            req_headers[header] = request.headers[header]

    client = request.app.state.client

    try:
        response = await client.post(
            downstream_server, headers=req_headers, json=payload
        )
    except httpx.RequestError:
        return create_json_rpc_error(
            body.id, -32000, "Downstream MCP server unavailable", 502
        )

    headers = {}
    for header in ("content-type", "mcp-session-id"):
        if header in response.headers:
            headers[header] = response.headers[header]

    return Response(
        content=response.content, status_code=response.status_code, headers=headers
    )


@app.post("/mcp")
async def root(request: Request, authorization: Annotated[str | None, Header()] = None):
    try:
        payload = await request.json()
        body = Body.model_validate(payload)
    except json.JSONDecodeError:
        return create_json_rpc_error(None, -32700, "Parse error")
    except (ValueError, ValidationError):
        return create_json_rpc_error(None, -32600, "Invalid Request")

    role = bearerRole(authorization)
    if role is None:
        return create_json_rpc_error(body.id, -32001, "Unauthorized Tool Call")

    is_admin = role == "admin"

    # Exclude non-admins from calling admin tools
    if body.method == "tools/call" and body.params is not None:
        param_name = body.params.get("name")
        if (
            isinstance(param_name, str)
            and param_name.startswith("admin_")
            and not is_admin
        ):
            return create_json_rpc_error(body.id, -32001, "Unauthorized Tool Call")

    if body.method == "tools/list":
        # Forward to downstream
        return await forward(payload, body, request)

    # For other methods like initialize, pass them through
    return await forward(payload, body, request)
