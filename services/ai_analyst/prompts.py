"""Loads the versioned, controlled system prompt (blueprint AI Analyst §17). Prompts are files
under `ai/prompts/`, never string-built at runtime, so every assessment can record exactly which
prompt version produced it and a reviewer can diff prompt changes like code changes.
"""

from functools import cache
from pathlib import Path

PROMPT_VERSION = "incident_analysis_v1"
_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "ai" / "prompts"


@cache
def load_system_prompt(version: str = PROMPT_VERSION) -> str:
    path = _PROMPT_DIR / f"{version}.txt"
    return path.read_text(encoding="utf-8")
