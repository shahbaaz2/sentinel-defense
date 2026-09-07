"""Contract for Falco's real default JSON alert output shape (`json_output: true` in falco.yaml)."""

from pydantic import BaseModel, Field


class FalcoAlert(BaseModel):
    output: str
    priority: str
    rule: str
    time: str
    output_fields: dict = Field(default_factory=dict)
