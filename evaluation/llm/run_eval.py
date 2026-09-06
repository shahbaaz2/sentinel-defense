"""Phase 5 AI Analyst evaluation harness (blueprint AI Analyst §20).

Runs every case in `evaluation/llm/cases.py` through a real (or mock, for a dry run) LLM provider
and reports: JSON/schema validity, hallucinated-reference rate, evidence/detection citation
accuracy, playbook-allowlist compliance, latency, and a soft classification-keyword match. This is
a standalone script, not a pytest suite - the pytest suites (tests/unit, tests/integration,
tests/adversarial) are the pass/fail gate; this harness is for humans reviewing model quality.

Usage:
    .venv/bin/python -m evaluation.llm.run_eval                  # real model (SENTINEL_LLM_MODEL)
    .venv/bin/python -m evaluation.llm.run_eval --provider mock   # fast structural dry run
"""

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ai.providers import build_provider
from ai.providers.base import StructuredCompletionError
from ai.providers.mock_provider import MockProvider
from ai.schemas import AIIncidentAssessment, DetectionReference, EvidenceReference
from evaluation.llm.cases import CASES, EvalCase
from services.ai_analyst.evidence import EvidencePack, evidence_pack_to_model_input
from services.ai_analyst.prompts import load_system_prompt
from services.ai_analyst.validation import ReferenceValidationError, validate_assessment


def _synthetic_mock_output(pack: EvidencePack) -> AIIncidentAssessment:
    """Only used for `--provider mock` - a self-consistent, non-hallucinating stand-in so the mock
    path exercises the harness's own plumbing (case loading, validation, reporting) rather than
    model quality. Never used for the real `mlx` provider path."""
    return AIIncidentAssessment(
        classification=pack.incident_category,
        confidence=0.5,
        summary=f"Synthetic mock summary for {pack.incident_id}.",
        affected_assets=[pack.primary_asset_id] if pack.primary_asset_id else [],
        evidence_refs=[
            EvidenceReference(event_id=e.event_id, relevance="mock") for e in pack.events[:1]
        ],
        detection_refs=[
            DetectionReference(detection_id=d.detection_id, relevance="mock")
            for d in pack.detections[:1]
        ],
        hypotheses=["mock hypothesis"],
        recommended_investigation_steps=["mock step"],
        attack_techniques=[],
        recommended_playbook_id=None,
        limitations=["mock provider - not a real model"],
    )


@dataclass
class CaseResult:
    case_id: str
    schema_valid: bool
    hallucination_free: bool
    keyword_match: bool
    latency_ms: int
    error: str | None
    classification: str | None
    confidence: float | None


async def _run_case(
    case: EvalCase, provider, max_tokens: int, timeout_seconds: float
) -> CaseResult:
    system_prompt = load_system_prompt()
    evidence = evidence_pack_to_model_input(case.pack)

    start = time.monotonic()
    try:
        result: AIIncidentAssessment = await provider.structured_completion(
            system_prompt=system_prompt,
            evidence=evidence,
            output_schema=AIIncidentAssessment,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
    except StructuredCompletionError as exc:
        return CaseResult(
            case_id=case.case_id,
            schema_valid=False,
            hallucination_free=False,
            keyword_match=False,
            latency_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            classification=None,
            confidence=None,
        )
    latency_ms = int((time.monotonic() - start) * 1000)

    hallucination_free = True
    error = None
    try:
        validate_assessment(result, case.pack)
    except ReferenceValidationError as exc:
        hallucination_free = False
        error = str(exc)

    haystack = f"{result.classification} {result.summary}".lower()
    keyword_match = not case.expect_classification_keywords or any(
        kw.lower() in haystack for kw in case.expect_classification_keywords
    )

    return CaseResult(
        case_id=case.case_id,
        schema_valid=True,
        hallucination_free=hallucination_free,
        keyword_match=keyword_match,
        latency_ms=latency_ms,
        error=error,
        classification=result.classification,
        confidence=result.confidence,
    )


async def run(
    provider_name: str, model_name: str, max_tokens: int, timeout_seconds: float
) -> list[CaseResult]:
    real_provider = None if provider_name == "mock" else build_provider(provider_name, model_name)
    results = []
    for case in CASES:
        provider = real_provider or MockProvider(fixed_output=_synthetic_mock_output(case.pack))
        result = await _run_case(case, provider, max_tokens, timeout_seconds)
        status = "OK" if result.schema_valid and result.hallucination_free else "FAIL"
        print(
            f"[{status}] {case.case_id:35s} schema={result.schema_valid} "
            f"hallucination_free={result.hallucination_free} keyword_match={result.keyword_match} "
            f"latency={result.latency_ms}ms"
        )
        if result.error:
            print(f"         error: {result.error}")
        results.append(result)
    return results


def summarize(results: list[CaseResult]) -> dict:
    n = len(results)
    return {
        "total_cases": n,
        "schema_valid_rate": sum(r.schema_valid for r in results) / n,
        "hallucination_free_rate": sum(r.hallucination_free for r in results) / n,
        "keyword_match_rate": sum(r.keyword_match for r in results) / n,
        "avg_latency_ms": sum(r.latency_ms for r in results) / n,
        "max_latency_ms": max(r.latency_ms for r in results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="mlx", choices=["mlx", "mock"])
    parser.add_argument("--model", default="mlx-community/Qwen3-4B-Instruct-2507-4bit")
    parser.add_argument("--max-tokens", type=int, default=1500)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--out", default=None, help="optional path to write JSON results")
    args = parser.parse_args()

    results = asyncio.run(run(args.provider, args.model, args.max_tokens, args.timeout_seconds))
    summary = summarize(results)

    print("\n=== SUMMARY ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(
            json.dumps({"summary": summary, "results": [asdict(r) for r in results]}, indent=2)
        )
        print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
