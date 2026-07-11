from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    name: str
    version: str


class ModuleInfo(BaseModel):
    key: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=32)
    status: Literal["planned", "building", "ready"]

