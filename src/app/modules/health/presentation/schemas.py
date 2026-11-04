from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    detail: str | None = None
