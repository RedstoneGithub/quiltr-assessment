from fastapi import FastAPI, Header, Response, Request
from fastapi.responses import JSONResponse
from typing import Annotated
from schema import Body
import httpx

downstream_server = "http://127.0.0.1:8002/mcp"

app = FastAPI()

def create_json_rpc_error(body:Body):
    json_rpc_error = {
        "jsonrpc": "2.0",
        "id": body.id,
        "error": {
            "code": -32001,
            "message": "Unauthorized Tool Call"
        }
    }
    return json_rpc_error

async def forward(body:Body, request:Request):
    async with httpx.AsyncClient() as client:
        req_headers = {}
        #print(request.headers)
        if "accept" in request.headers:
            req_headers["accept"] = request.headers.get("accept")
        if "mcp-session-id" in request.headers:
            req_headers["mcp-session-id"] = request.headers.get("mcp-session-id")

        response = await client.post(
            downstream_server,
            headers = req_headers,
            json=body.model_dump()
        )

        headers = {}
        if "content-type" in response.headers:
            headers["content-type"] = response.headers.get("content-type")
        if "mcp-session-id" in response.headers:
            headers["mcp-session-id"] = response.headers.get("mcp-session-id")

        return Response(
            content = response.content,
            status_code = response.status_code,
            headers = headers
        )

@app.post("/mcp")
async def root(body:Body, request: Request, authorization: Annotated[str | None, Header()] = None):
    if not authorization:
        return create_json_rpc_error(body)
    if not authorization.startswith("Bearer "):
        return create_json_rpc_error(body)
    bearer = authorization.removeprefix("Bearer ")
    bearer.strip()

    is_admin = bearer == "admin"

    print(body)

    # Exclude non-admins from calling admin tools
    if body.method == "tools/call":
        if body.params is not None:
            param_name = body.params.get("name")
            if isinstance(param_name, str):
                if param_name.startswith("admin_"):
                    if not is_admin:
                        return create_json_rpc_error(body)

    if body.method == "tools/list":
        # Forward to downstream
        return await forward(body, request)

    # For other methods like initialize, pass them through
    return await forward(body, request)