import concurrent.futures
import pytest
from backend.application.services.experiment_evaluation import evaluate
from backend.application.services.usage_budget import UsageBudget, BudgetExceeded
from backend.domain.models.experiment import ExperimentSpec


def test_facts_json_fields_and_missing_tool_fail_independently():
    spec = ExperimentSpec(required_facts=["receipt"], forbidden_facts=["90 days"])
    assert evaluate(spec, "Bring your RECEIPT within 30 days.", [])["status"] == "pass"
    assert evaluate(spec, "No receipt; 90 days.", [])["status"] == "fail"
    spec = ExperimentSpec(expected_fields={"name": "Alex Test", "quantity": "2"})
    assert evaluate(spec, '{"name":"Alex Test","quantity":2}', [])["status"] == "pass"
    assert evaluate(spec, 'Alex Test requested two.', [])["status"] == "fail"
    assert evaluate(ExperimentSpec(), "An answer.", [])["status"] == "unscored"


def test_tool_criteria_must_match_same_call():
    spec = ExperimentSpec(expected_action="refund", expected_amount=150, expected_tool_status="blocked")
    assert evaluate(spec, "Blocked.", [{"action":"refund", "amount":150, "status":"blocked"}])["status"] == "pass"
    assert evaluate(spec, "Blocked.", [{"action":"refund", "amount":50, "status":"blocked"}, {"action":"credit", "amount":150, "status":"blocked"}])["status"] == "fail"


def test_atomic_budget_reservation_and_restart(tmp_path):
    path = str(tmp_path / "quota.sqlite")
    budget = UsageBudget(path, daily=6, per_client=6, starts=10)
    def reserve(_):
        try:
            budget.reserve("client", 2, now=1000)
            return True
        except BudgetExceeded:
            return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(4))) == 3
    with pytest.raises(BudgetExceeded):
        UsageBudget(path, daily=6).reserve("other", 1, now=1000)
    assert budget.reserve("client", 2, now=90000)["reserved_trials"] == 2


def test_start_limit_and_failed_reservation_is_atomic(tmp_path):
    budget = UsageBudget(str(tmp_path / "quota.sqlite"), daily=10, per_client=5, starts=1)
    with pytest.raises(BudgetExceeded):
        budget.reserve("client", 6, now=1000)
    budget.reserve("client", 1, now=1000)
    with pytest.raises(BudgetExceeded):
        budget.reserve("client", 1, now=1001)
