from pydantic import BaseModel, StringConstraints
from typing import Annotated, Any

class Body(BaseModel):
    jsonrpc: str
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None