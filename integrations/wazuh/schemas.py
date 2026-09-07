"""Contract for the subset of a real Wazuh alert's fields this integration reads - the well-known
`rule`/`agent`/`decoder`/`data` shape Wazuh emits to `alerts.json` and its Indexer, not a
Sentinel invention. See docs/integrations.md for where this was verified against real Wazuh
documentation/exported samples."""

from pydantic import BaseModel, Field


class WazuhMitre(BaseModel):
    id: list[str] = Field(default_factory=list)
    tactic: list[str] = Field(default_factory=list)
    technique: list[str] = Field(default_factory=list)


class WazuhRule(BaseModel):
    id: str
    level: int
    description: str
    groups: list[str] = Field(default_factory=list)
    mitre: WazuhMitre | None = None


class WazuhAgent(BaseModel):
    id: str
    name: str
    ip: str | None = None


class WazuhAlert(BaseModel):
    id: str
    timestamp: str
    rule: WazuhRule
    agent: WazuhAgent
    decoder: dict | None = None
    data: dict = Field(default_factory=dict)
    location: str | None = None
    full_log: str | None = None
