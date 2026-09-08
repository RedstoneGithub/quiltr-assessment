from contextlib import asynccontextmanager
import os
from typing import Annotated, Any

from fastapi import FastAPI, Header, Response, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from schema import Body
import httpx

downstream_server = os.getenv(
    "DOWNSTREAM_MCP_URL",
    "http://127.0.0.1:8002/mcp"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=10)
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan)


def create_json_rpc_error(requestId: Any, code: int, message: str,
                          statusCode: int = 200):
    return JSONResponse(
        status_code=statusCode,
        content={
            "jsonrpc": "2.0",
            "id": requestId,
            "error": {
                "code": code,
                "message": message
            }
        }
    )


async def forward(payload: dict, body: Body, request: Request):
    req_headers = {}
    for header in (
        "accept",
        "mcp-session-id",
        "mcp-protocol-version",
        "last-event-id"
    ):
        if header in request.headers:
            req_headers[header] = request.headers[header]

    client = request.app.state.client

    try:
        response = await client.post(
            downstream_server,
            headers=req_headers,
            json=payload
        )
    except httpx.RequestError:
        return create_json_rpc_error(
            body.id,
            -32000,
            "Downstream MCP server unavailable",
            502
        )

    headers = {}
    for header in ("content-type", "mcp-session-id"):
        if header in response.headers:
            headers[header] = response.headers[header]

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=headers
    )

@app.post("/mcp")
async def root(
    request: Request,
    authorization: Annotated[str | None, Header()] = None
):
    try:
        payload = await request.json()
        body = Body.model_validate(payload)
    except (ValueError, ValidationError):
        return create_json_rpc_error(None, -32600, "Invalid Request")

    if not authorization or not authorization.startswith("Bearer "):
        return create_json_rpc_error(
            body.id,
            -32001,
            "Unauthorized Tool Call"
        )

    role = authorization.removeprefix("Bearer ").strip()
    is_admin = role == "admin"

    # Exclude non-admins from calling admin tools
    if body.method == "tools/call":
        if body.params is not None:
            param_name = body.params.get("name")
            if isinstance(param_name, str):
                if param_name.startswith("admin_"):
                    if not is_admin:
                        return create_json_rpc_error(
                            body.id,
                            -32001,
                            "Unauthorized Tool Call"
                        )

    if body.method == "tools/list":
        # Forward to downstream
        return await forward(payload, body, request)

    # For other methods like initialize, pass them through
    return await forward(payload, body, request)
