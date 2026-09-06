"""Hallucination / reference validation (blueprint AI Analyst §9). Pydantic schema validation
(see `ai/schemas.py`) only proves the *shape* of the model's output is right; this module proves
its *content* is grounded - every event_id, detection_id, and asset_id the model cited must exist
in the exact evidence pack it was given. Target: hallucinated reference acceptance rate = 0%.
"""

from ai.schemas import AIIncidentAssessment
from services.ai_analyst.evidence import EvidencePack


class ReferenceValidationError(Exception):
    """Raised when an AIIncidentAssessment cites an ID that does not exist in the evidence pack it
    was produced from. Callers must reject the assessment (validation_status =
    REJECTED_HALLUCINATION), not display it."""


def validate_assessment(assessment: AIIncidentAssessment, pack: EvidencePack) -> None:
    valid_event_ids = {e.event_id for e in pack.events}
    valid_detection_ids = {d.detection_id for d in pack.detections}
    valid_asset_ids = {pack.primary_asset_id} if pack.primary_asset_id else set()

    for evidence_ref in assessment.evidence_refs:
        if evidence_ref.event_id not in valid_event_ids:
            raise ReferenceValidationError(
                f"cited event_id {evidence_ref.event_id!r} is not in this incident's evidence pack"
            )
    for detection_ref in assessment.detection_refs:
        if detection_ref.detection_id not in valid_detection_ids:
            raise ReferenceValidationError(
                f"cited detection_id {detection_ref.detection_id!r} is not in this incident's "
                "evidence pack"
            )
    for asset_id in assessment.affected_assets:
        if asset_id not in valid_asset_ids:
            raise ReferenceValidationError(
                f"cited affected_asset {asset_id!r} is not in this incident's evidence pack"
            )
    if (
        assessment.recommended_playbook_id is not None
        and assessment.recommended_playbook_id not in pack.available_playbook_ids
    ):
        raise ReferenceValidationError(
            f"recommended_playbook_id {assessment.recommended_playbook_id!r} is not in the "
            "available playbook allowlist"
        )
