import pytest

from apps.demo_control.scenarios import ScenarioDefinition, list_scenarios, load_scenario


@pytest.mark.parametrize(
    "scenario_id", ["SCN-001", "SCN-002", "SCN-003", "SCN-004", "SCN-010"]
)
def test_every_required_scenario_loads_and_validates(scenario_id):
    scenario = load_scenario(scenario_id)
    assert isinstance(scenario, ScenarioDefinition)
    assert scenario.id == scenario_id
    assert scenario.risk_level == "safe_lab_only"
    assert len(scenario.steps) >= 1
    assert len(scenario.success_conditions) >= 1


def test_list_scenarios_finds_all_five():
    scenarios = list_scenarios()
    ids = {s.id for s in scenarios}
    assert ids == {"SCN-001", "SCN-002", "SCN-003", "SCN-004", "SCN-010"}


def test_scn010_expects_five_distinct_rules():
    scenario = load_scenario("SCN-010")
    rule_ids = [d.rule_id for d in scenario.expected_observations.sentinel.detections]
    assert len(rule_ids) == len(set(rule_ids)) == 5


def test_scn010_does_not_force_single_incident():
    """The flagship scenario must not hard-code a single-incident expectation - it should require
    a minimum consistent with real, unmerged correlation output (see DECISIONS.md)."""
    scenario = load_scenario("SCN-010")
    assert scenario.expected_observations.sentinel.incidents.min_count >= 3


def test_missing_scenario_raises():
    with pytest.raises(FileNotFoundError):
        load_scenario("SCN-999")


def test_scn004_uses_targets_list_not_repeat():
    scenario = load_scenario("SCN-004")
    step = scenario.steps[0]
    assert step.targets is not None
    assert len(step.targets) == 5


def test_scn001_uses_repeat_not_targets():
    scenario = load_scenario("SCN-001")
    step = scenario.steps[0]
    assert step.target == "j.rivera"
    assert step.repeat == 3
