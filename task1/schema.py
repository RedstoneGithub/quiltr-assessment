from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints
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

class CustomerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: CustomerId

class Refund(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: CustomerId
    amount: Amount
    reason: Reason
