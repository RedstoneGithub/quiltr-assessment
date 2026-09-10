from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    WithJsonSchema
)

CustomerId = Annotated[
    str,
    StringConstraints(pattern=r"^CUST-\d{5}$")
]

Amount = Annotated[
    float,
    Field(gt=0, allow_inf_nan=False)
]

Reason = Annotated[
    str,
    Field(min_length=10)
]

# These types expose the same constraints in tools/list. Validation is still
# performed by the models below so invalid input can return JSON-RPC -32602.
CustomerIdInput = Annotated[
    str,
    WithJsonSchema({
        "type": "string",
        "pattern": r"^CUST-\d{5}$"
    })
]

AmountInput = Annotated[
    float,
    WithJsonSchema({
        "type": "number",
        "exclusiveMinimum": 0
    })
]

ReasonInput = Annotated[
    str,
    WithJsonSchema({
        "type": "string",
        "minLength": 10
    })
]

class CustomerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: CustomerId

class Refund(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: CustomerId
    amount: Amount
    reason: Reason
