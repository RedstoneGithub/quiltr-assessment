from mcp import MCPError
from mcp.server import MCPServer
from mcp.types import INVALID_PARAMS
from schema import (
    AmountInput,
    CustomerIdInput,
    CustomerRecord,
    ReasonInput,
    Refund
)
from pydantic import ValidationError

mcp = MCPServer("Test")

@mcp.tool()
def get_customer_record(customer_id: CustomerIdInput) -> dict:
    """Get a customer record using a CUST-XXXXX customer ID."""
    try:
        customer = CustomerRecord(customer_id=customer_id)
    except ValidationError as e:
        raise MCPError(
            code=INVALID_PARAMS,
            message="Invalid customer record parameters",
            data=e.errors(include_url=False)
        ) from e
    return customer.model_dump()

@mcp.tool()
def trigger_refund(customer_id: CustomerIdInput, amount: AmountInput,
                   reason: ReasonInput) -> dict:
    """Trigger a positive refund with a reason of at least 10 characters."""
    try:
        refund = Refund(customer_id=customer_id, amount=amount, reason=reason)
    except ValidationError as e:
        raise MCPError(
            code=INVALID_PARAMS,
            message="Invalid refund parameters",
            data=e.errors(include_url=False)
        ) from e
    return refund.model_dump()


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
