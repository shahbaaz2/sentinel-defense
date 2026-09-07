"""Phase 7: the executor's action/rollback/verification registries are closed sets, checked
against each other and against the real playbook catalog - no DB, no HTTP, pure data. This is what
guarantees "no arbitrary shell/SQL/SSH/firewall interface exists" (blueprint DoD): every capability
the executor has is one of these three dicts, and this test enumerates all of them.
"""

from services.policy_engine.actions import ACTION_REGISTRY
from services.policy_engine.playbooks import list_playbooks
from services.response_executor.registry import ACTION_HANDLERS
from services.response_executor.rollback import ROLLBACK_HANDLERS
from services.response_executor.verifier import VERIFIERS

FORBIDDEN_NAMES = (
    "execute_shell",
    "ssh",
    "execute_sql",
    "docker_exec",
    "firewall",
    "run_script",
    "subprocess",
    "os.system",
)


def test_every_playbook_action_has_a_registered_handler():
    for playbook in list_playbooks():
        for action in playbook.actions:
            assert action.action_id in ACTION_HANDLERS, (
                f"{playbook.id} references {action.action_id!r} with no executor handler"
            )


def test_action_handlers_are_a_subset_of_the_policy_engine_action_registry():
    """The executor can never claim to handle an action_id the Phase 6 registry doesn't declare -
    that would be a capability invented outside the reviewed, closed catalog."""
    assert set(ACTION_HANDLERS.keys()) <= set(ACTION_REGISTRY.keys())


def test_restore_workload_network_is_rollback_only():
    """Exists in the Phase 6 action registry as a schema/description, but no playbook lists it as
    a forward step - it only ever runs as quarantine_workload's rollback."""
    assert "restore_workload_network" not in ACTION_HANDLERS
    for playbook in list_playbooks():
        assert all(a.action_id != "restore_workload_network" for a in playbook.actions)


def test_rollback_handlers_are_a_subset_of_action_handlers():
    """Nothing can be "rolled back" that wasn't itself a real forward action."""
    assert set(ROLLBACK_HANDLERS.keys()) <= set(ACTION_HANDLERS.keys())


def test_actions_declared_reversible_and_rollback_capable_have_a_rollback_handler():
    for action_id, definition in ACTION_REGISTRY.items():
        if definition.reversible and definition.rollback_capable:
            assert action_id in ROLLBACK_HANDLERS, (
                f"{action_id} claims rollback_capable=True but has no rollback handler"
            )


def test_actions_without_rollback_capability_have_no_handler():
    """Never claim rollback support for an action that cannot actually be restored (blueprint §14)
    - the inverse of the check above."""
    for action_id, definition in ACTION_REGISTRY.items():
        if not definition.rollback_capable:
            assert action_id not in ROLLBACK_HANDLERS, (
                f"{action_id} is declared not rollback_capable but has a rollback handler anyway"
            )


def test_every_action_expected_verification_has_a_verifier():
    for action_id in ACTION_HANDLERS:
        expected = ACTION_REGISTRY[action_id].expected_verification
        assert expected in VERIFIERS, f"{action_id}'s expected_verification {expected!r} unhandled"


def test_no_forbidden_execution_primitive_anywhere_in_the_executor_source():
    import inspect

    from services.response_executor import executor, registry, rollback, targets, verifier

    source = "".join(
        inspect.getsource(m) for m in (executor, registry, rollback, targets, verifier)
    )
    lowered = source.lower()
    for forbidden in FORBIDDEN_NAMES:
        assert forbidden not in lowered, f"forbidden execution primitive found: {forbidden!r}"
