"""Provider factory - the one place that knows which concrete `LLMProvider` implementation to
build for a given `SENTINEL_LLM_PROVIDER` value. Everything downstream (services/ai_analyst,
apps/api) imports `get_provider`, never a concrete provider class.
"""

from ai.providers.base import LLMProvider
from ai.providers.mock_provider import MockProvider

_provider_singleton: LLMProvider | None = None
_provider_singleton_key: tuple[str, str] | None = None


def build_provider(provider_name: str, model_name: str) -> LLMProvider:
    if provider_name == "mock":
        return MockProvider()
    if provider_name == "mlx":
        from ai.providers.mlx_provider import MLXProvider

        return MLXProvider(model_name=model_name)
    raise ValueError(f"Unknown SENTINEL_LLM_PROVIDER: {provider_name!r}")


def get_provider(provider_name: str, model_name: str) -> LLMProvider:
    """Process-wide singleton per (provider_name, model_name) - the whole point of the MLX
    provider being a singleton is that the 16GB Lite profile must never load the model twice."""
    global _provider_singleton, _provider_singleton_key
    key = (provider_name, model_name)
    if _provider_singleton is None or _provider_singleton_key != key:
        _provider_singleton = build_provider(provider_name, model_name)
        _provider_singleton_key = key
    return _provider_singleton


def reset_provider_singleton() -> None:
    """Test-only escape hatch - lets tests swap in a fresh MockProvider between cases instead of
    reusing whatever singleton a previous test created."""
    global _provider_singleton, _provider_singleton_key
    _provider_singleton = None
    _provider_singleton_key = None
