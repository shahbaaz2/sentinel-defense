"""Phase 5: the controlled system prompt must actually state the trust-boundary rules (blueprint
AI Analyst §7, §17) - this is a cheap regression guard against someone editing the prompt file and
silently dropping the rules the prompt-injection test at tests/adversarial/ depends on."""

from services.ai_analyst.prompts import PROMPT_VERSION, load_system_prompt


def test_prompt_version_file_exists_and_is_nonempty():
    text = load_system_prompt()
    assert len(text) > 200


def test_prompt_version_matches_loaded_file():
    assert PROMPT_VERSION == "incident_analysis_v1"
    assert load_system_prompt(PROMPT_VERSION) == load_system_prompt()


def test_prompt_states_evidence_is_untrusted():
    text = load_system_prompt().lower()
    assert "untrusted" in text or "data to analyze" in text.lower()


def test_prompt_forbids_state_changes():
    text = load_system_prompt().lower()
    for phrase in ("change an incident's severity", "cannot and must not"):
        assert phrase in text


def test_prompt_forbids_id_invention():
    text = load_system_prompt().lower()
    assert "invent" in text


def test_prompt_is_cached():
    assert load_system_prompt() is load_system_prompt()
