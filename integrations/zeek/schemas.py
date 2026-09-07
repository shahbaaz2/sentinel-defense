"""Contract for the subset of real Zeek JSON log lines this integration reads (`LogAscii::use_json
= T`). Each model validates only the fields the mapper actually uses - a line missing a field this
model requires is skipped, not fabricated (see mapper.py)."""

from pydantic import BaseModel, Field


class ZeekConnRecord(BaseModel):
    ts: float
    uid: str
    id_orig_h: str = Field(alias="id.orig_h")
    id_orig_p: int = Field(alias="id.orig_p")
    id_resp_h: str = Field(alias="id.resp_h")
    id_resp_p: int = Field(alias="id.resp_p")
    proto: str
    service: str | None = None
    conn_state: str | None = None

    model_config = {"populate_by_name": True}


class ZeekDnsRecord(BaseModel):
    ts: float
    uid: str
    id_orig_h: str = Field(alias="id.orig_h")
    id_orig_p: int = Field(alias="id.orig_p")
    id_resp_h: str = Field(alias="id.resp_h")
    id_resp_p: int = Field(alias="id.resp_p")
    query: str
    qtype_name: str | None = None
    rcode_name: str | None = None
    answers: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ZeekHttpRecord(BaseModel):
    ts: float
    uid: str
    id_orig_h: str = Field(alias="id.orig_h")
    id_orig_p: int = Field(alias="id.orig_p")
    id_resp_h: str = Field(alias="id.resp_h")
    id_resp_p: int = Field(alias="id.resp_p")
    method: str | None = None
    host: str | None = None
    uri: str | None = None
    status_code: int | None = None
    user_agent: str | None = None

    model_config = {"populate_by_name": True}
