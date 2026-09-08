from pydantic import BaseModel, ConfigDict
from typing import Any, Literal

class Body(BaseModel):
    model_config = ConfigDict(extra="allow")

    jsonrpc: Literal["2.0"]
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None
