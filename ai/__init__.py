"""Phase 5: local AI Analyst runtime - provider abstraction and controlled prompts.

Nothing in `ai/` may talk to a cloud LLM API. Nothing in `apps/` or `domain/` should import
`ai/providers/mlx_provider.py` directly - go through `ai.providers.base.LLMProvider` and the
factory in `ai.providers.get_provider`, so a future provider is a pure addition, not a rewrite.
"""
