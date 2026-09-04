from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from schema import CustomerRecord, Refund
from pydantic import ValidationError

mcp = MCPServer("Test")

@mcp.tool()
def get_customer_record(customer_id: str):
    try:
        customer = CustomerRecord(customer_id=customer_id)
    except ValidationError as e:
        return ToolError(e)
    return customer

@mcp.tool()
def trigger_refund(customer_id: str, amount: float, reason: str):
    try:
        refund = Refund(customer_id=customer_id, amount=amount, reason=reason)
    except ValidationError as e:
        return ToolError(e)
    return refund