from mcp.server import MCPServer

mcp = MCPServer("Task2")

@mcp.tool()
def test(testStr: str) -> str:
    return testStr + "abc"

@mcp.tool()
def admin_test(testStr: str) -> str:
    return testStr + "def"

app = mcp.streamable_http_app()