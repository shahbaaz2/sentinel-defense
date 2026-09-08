"""Phase 5: LLMProvider abstraction and the mock provider used everywhere except the live MLX
verification. Also covers the provider factory's singleton behaviour - the whole point of which is
never loading two large models concurrently on the 16GB Lite profile."""

import pytest

from ai.providers import build_provider, get_provider, reset_provider_singleton
from ai.providers.base import ProviderStatus, StructuredCompletionError
from ai.providers.mock_provider import MockProvider
from ai.schemas import AIIncidentAssessment


def _valid_assessment() -> AIIncidentAssessment:
    return AIIncidentAssessment(
        classification="benign",
        confidence=0.5,
        summary="test",
        affected_assets=[],
        evidence_refs=[],
        detection_refs=[],
        hypotheses=[],
        recommended_investigation_steps=[],
        attack_techniques=[],
        recommended_playbook_id=None,
        limitations=[],
    )


async def test_mock_provider_returns_fixed_output():
    provider = MockProvider(fixed_output=_valid_assessment())
    result = await provider.structured_completion(
        system_prompt="sys",
        evidence={},
        output_schema=AIIncidentAssessment,
        max_tokens=100,
        timeout_seconds=5.0,
    )
    assert result.classification == "benign"
    assert await provider.get_status() == ProviderStatus.READY


async def test_mock_provider_raises_configured_error():
    provider = MockProvider(raise_error=StructuredCompletionError("simulated timeout"))
    with pytest.raises(StructuredCompletionError, match="simulated timeout"):
        await provider.structured_completion(
            system_prompt="sys",
            evidence={},
            output_schema=AIIncidentAssessment,
            max_tokens=100,
            timeout_seconds=5.0,
        )


async def test_mock_provider_with_no_config_raises():
    provider = MockProvider()
    with pytest.raises(StructuredCompletionError):
        await provider.structured_completion(
            system_prompt="sys",
            evidence={},
            output_schema=AIIncidentAssessment,
            max_tokens=100,
            timeout_seconds=5.0,
        )


def test_mock_provenance_has_no_local_model():
    provider = MockProvider()
    provenance = provider.get_provenance()
    assert provenance.model_provider == "mock"
    assert provenance.local_path is None


def test_build_provider_unknown_name_raises():
    with pytest.raises(ValueError, match="Unknown SENTINEL_LLM_PROVIDER"):
        build_provider("openai", "gpt-4")


def test_build_provider_rejects_unlisted_names_by_construction():
    """`build_provider` only has branches for {mock, mlx, deepseek} - a typo'd or malicious config
    value fails safe rather than falling through to something unintended. `deepseek` (Phase 8+) is
    deliberately allowlisted for cloud deployments with no Apple-Silicon host; every other cloud
    name stays rejected exactly like before."""
    for forbidden in ("openai", "anthropic", "gemini", "huggingface-inference"):
        with pytest.raises(ValueError):
            build_provider(forbidden, "some-model")


def test_build_provider_deepseek_is_allowlisted():
    provider = build_provider("deepseek", "deepseek-chat", api_key="test-key")
    assert provider.provider_name == "deepseek"


def test_deepseek_provider_provenance_reports_cloud_runtime():
    provider = build_provider("deepseek", "deepseek-chat", api_key="test-key")
    provenance = provider.get_provenance()
    assert provenance.model_provider == "deepseek"
    assert "cloud" in provenance.runtime.lower()
    assert provenance.local_path is None


def test_get_provider_singleton_reused_for_same_key():
    reset_provider_singleton()
    a = get_provider("mock", "irrelevant-model")
    b = get_provider("mock", "irrelevant-model")
    assert a is b
    reset_provider_singleton()


def test_get_provider_rebuilds_on_key_change():
    reset_provider_singleton()
    a = get_provider("mock", "model-a")
    b = get_provider("mock", "model-b")
    assert a is not b
    reset_provider_singleton()
