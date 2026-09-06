from datetime import datetime

from pydantic import BaseModel, Field


class AssetOut(BaseModel):
    asset_id: str
    name: str
    asset_type: str
    mission_role: str
    criticality: int
    dependencies: list[str]
    status: str
    network_state: str
    rollback_supported: bool
    classification: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    user_type: str
    status: str
    classification: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    token_id: str
    owner_user_id: str
    token_type: str
    valid: bool
    created_at: datetime
    revoked_at: datetime | None
    classification: str

    model_config = {"from_attributes": True}


class MissionRecordOut(BaseModel):
    record_id: str
    title: str
    body: str
    owner_user_id: str
    created_at: datetime
    classification: str

    model_config = {"from_attributes": True}


class TelemetryOut(BaseModel):
    sample_id: str
    asset_id: str
    battery: int
    link_quality: int
    latitude: float | None
    longitude: float | None
    generated_at: datetime
    classification: str

    model_config = {"from_attributes": True}


class AuditEventOut(BaseModel):
    audit_id: str
    timestamp: datetime
    actor_type: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    detail: dict
    severity: str
    scenario_id: str | None
    classification: str

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str = Field(max_length=256)
    password: str = Field(max_length=256)


class LoginResponse(BaseModel):
    success: bool
    user_id: str | None = None
    reason: str | None = None


class SystemStateOut(BaseModel):
    status: str
    """Overall MissionNet status: nominal, degraded, containment_in_progress, recovering."""
    degraded_assets: list[str]
    quarantined_assets: list[str]
    classification: str = "SYNTHETIC"
