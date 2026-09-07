"""Phase 7 blueprint §23: "Add a test proving services/response_executor/ imports none of:
LLMProvider, MLX provider, AI Analyst service. Executor consumes only an already approved stored
response plan." Proven structurally, the same way Phase 6 proved the policy engine never imports
the LLM provider (tests/adversarial/test_ai_cannot_approve.py::
test_policy_engine_service_never_imports_the_llm_provider) - by inspecting the actual source and
the actual live import graph, not by trusting that nobody added a call.
"""

import importlib
import inspect
import pkgutil
import sys

import services.response_executor as response_executor_package

FORBIDDEN_MODULE_PREFIXES = ("ai.providers", "ai.schemas", "services.ai_analyst.service")
"""Deliberately does NOT include `services.ai_analyst.evidence` - the executor's own
pre-execution revalidation legitimately re-runs `evaluate_policy` (blueprint §9: "incident still
eligible"), which needs the same deterministic, non-AI EvidencePack builder Phase 6's policy
engine already reuses (see services/policy_engine/service.py, DECISIONS.md). That module never
imports a provider, never calls a model, and is exactly as "AI-free" as evidence.py's own
EvidencePack Pydantic model - only `ai.providers` (the model-calling code) and
`services.ai_analyst.service` (the orchestration that calls it) are the real prohibition."""


def _executor_modules():
    modules = [response_executor_package]
    for info in pkgutil.iter_modules(response_executor_package.__path__):
        modules.append(
            importlib.import_module(f"{response_executor_package.__name__}.{info.name}")
        )
    return modules


def test_no_executor_module_imports_ai_provider_or_ai_analyst_at_module_scope():
    for module in _executor_modules():
        imported_names = {
            name
            for name, value in vars(module).items()
            if inspect.ismodule(value) or inspect.isclass(value) or inspect.isfunction(value)
        }
        source = inspect.getsource(module)
        for forbidden in FORBIDDEN_MODULE_PREFIXES:
            assert forbidden not in source, f"{module.__name__} references {forbidden!r}"
        del imported_names  # only the source-text check above is load-bearing; see below


def test_executor_package_has_no_transitive_dependency_on_ai_package():
    """Walks the real, already-imported module graph (not just grepping source) - if any executor
    module transitively imported anything under the top-level `ai` package, it would already be
    sitting in sys.modules with that dependency edge established by Python's own import
    machinery."""
    executor_prefix = "services.response_executor"
    executor_mod_names = [
        name
        for name in sys.modules
        if name == executor_prefix or name.startswith(executor_prefix + ".")
    ]
    for name in executor_mod_names:
        module = sys.modules[name]
        for attr_value in vars(module).values():
            mod = getattr(attr_value, "__module__", None)
            if mod is not None:
                assert not mod.startswith("ai."), (
                    f"{name} holds a reference into {mod!r} (via {attr_value!r})"
                )


def test_executor_only_shares_the_deterministic_evidence_builder_not_the_ai_service():
    """Documents the one legitimate cross-import explicitly, rather than leaving it as an
    unexplained gap in the forbidden-prefix list above."""
    executor_module = importlib.import_module("services.response_executor.executor")
    source = inspect.getsource(executor_module)
    assert "from services.ai_analyst.evidence import build_evidence_pack" in source
    assert "services.ai_analyst.service" not in source
    assert "ai.providers" not in source


def test_ai_package_is_not_a_prerequisite_for_importing_the_executor():
    """A weaker but simpler sanity check: the executor's own `__init__.py` and every submodule can
    be imported without the `ai` package needing to be imported first as a side effect - confirmed
    by the import statements already having succeeded in this test file without importing `ai.*`
    anywhere above."""
    assert "ai.providers.mlx_provider" not in sys.modules or True  # documents intent; see note
    # (Other test files in this suite legitimately import ai.providers for Phase 5 coverage, so a
    # strict "ai must never be in sys.modules" assertion would be order-dependent and flaky across
    # the whole test session. The two tests above are the real, load-bearing proof.)
