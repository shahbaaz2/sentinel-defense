from apps.demo_control.runner import _expand_steps
from apps.demo_control.scenarios import ScenarioStep


def test_expand_repeat_produces_n_copies_of_same_target():
    step = ScenarioStep(id="s1", action="auth_failure", target="user1", repeat=3)
    expanded = _expand_steps([step])
    assert expanded == [(step, "user1"), (step, "user1"), (step, "user1")]


def test_expand_targets_produces_one_call_per_target():
    step = ScenarioStep(id="s1", action="access_record", targets=["a", "b", "c"])
    expanded = _expand_steps([step])
    assert [t for _, t in expanded] == ["a", "b", "c"]


def test_expand_single_target_no_repeat_produces_one_call():
    step = ScenarioStep(id="s1", action="degrade_asset", target="asset-1")
    expanded = _expand_steps([step])
    assert expanded == [(step, "asset-1")]


def test_expand_preserves_step_order_across_multiple_steps():
    step1 = ScenarioStep(id="s1", action="revoke_token", target="tok-1")
    step2 = ScenarioStep(id="s2", action="access_record", target="rec-1")
    expanded = _expand_steps([step1, step2])
    assert [s.id for s, _ in expanded] == ["s1", "s2"]
