from mcp.server import MCPServer

mcp = MCPServer("Task2")

@mcp.tool()
def test(testStr: str) -> str:
    return testStr + "abc"

@mcp.tool()
def admin_test(testStr: str) -> str:
    return testStr + "def"

app = mcp.streamable_http_app()


def main():
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8002
    )


if __name__ == "__main__":
    main()
