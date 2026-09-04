from typing import Literal, Annotated

from pydantic import (
    BaseModel,
    Field,
    StringConstraints
)

CustomerId = Annotated[
    str,
    StringConstraints(pattern=r"^CUST-\d{5}$")
]

Amount = Annotated[
    float,
    Field(gt=0)
]

Reason = Annotated[
    str,
    Field(min_length=10)
]

class CustomerRecord(BaseModel):
    customer_id: CustomerId
        
class Refund(BaseModel):
    customer_id: CustomerId
    amount: Amount
    reason: Reason