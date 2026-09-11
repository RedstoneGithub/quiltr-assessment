from mcp import MCPError
from mcp.server import MCPServer
from mcp.types import INVALID_PARAMS
from pydantic import ValidationError

try:
    from .schema import (
        AmountInput,
        CustomerIdInput,
        CustomerRecord,
        ReasonInput,
        Refund,
    )
except ImportError:
    from schema import (
        AmountInput,
        CustomerIdInput,
        CustomerRecord,
        ReasonInput,
        Refund,
    )


TOOL_INPUT_MODELS = {
    "get_customer_record": CustomerRecord,
    "trigger_refund": Refund,
}


class StrictToolValidationMiddleware:
    """Validate raw tool arguments before the SDK can coerce their types."""

    async def __call__(self, context, call_next):
        if context.method == "tools/call":
            params = context.params
            if isinstance(params, dict):
                tool_name = params.get("name")
                arguments = params.get("arguments")
            else:
                tool_name = getattr(params, "name", None)
                arguments = getattr(params, "arguments", None)

            input_model = TOOL_INPUT_MODELS.get(tool_name)
            if input_model is not None:
                try:
                    input_model.model_validate(arguments)
                except ValidationError as error:
                    raise MCPError(
                        code=INVALID_PARAMS,
                        message="Invalid tool parameters",
                        data=error.errors(include_url=False),
                    ) from error

        return await call_next(context)


mcp = MCPServer("FDE Assessment", middleware=[StrictToolValidationMiddleware()])


@mcp.tool()
def get_customer_record(customer_id: CustomerIdInput) -> dict:
    """Get a customer record using a CUST-XXXXX customer ID."""
    try:
        customer = CustomerRecord(customer_id=customer_id)
    except ValidationError as e:
        raise MCPError(
            code=INVALID_PARAMS,
            message="Invalid customer record parameters",
            data=e.errors(include_url=False),
        ) from e
    return customer.model_dump()


@mcp.tool()
def trigger_refund(
    customer_id: CustomerIdInput, amount: AmountInput, reason: ReasonInput
) -> dict:
    """Trigger a positive refund with a reason of at least 10 characters."""
    try:
        refund = Refund(customer_id=customer_id, amount=amount, reason=reason)
    except ValidationError as e:
        raise MCPError(
            code=INVALID_PARAMS,
            message="Invalid refund parameters",
            data=e.errors(include_url=False),
        ) from e
    return refund.model_dump()


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
