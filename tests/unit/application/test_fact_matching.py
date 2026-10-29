import pytest
from backend.application.services.experiment_evaluation import evaluate
from backend.domain.models.experiment import ExperimentSpec

@pytest.mark.parametrize('answer,passed', [
    ('Returns are accepted for 30 days.', True),
    ('Returns are accepted for thirty days.', True),
    ('Returns are accepted for 130 days.', False),
    ('Returns are not accepted for 30 days.', False),
    ('The 30 days policy is not valid.', False),
    ('Returns take 30 hours.', False),
    ('Returns take 30.5 days.', False),
])
def test_quantity_and_negation(answer, passed):
    result = evaluate(ExperimentSpec(required_facts=['30 days']), answer, [])
    assert (result['status'] == 'pass') is passed

def test_alternative_wording_and_negated_forbidden_claim():
    spec = ExperimentSpec(acceptable_facts=[['receipt', 'proof of purchase']], forbidden_facts=['90 days'])
    assert evaluate(spec, 'Bring proof of purchase. You cannot return after 90 days.', [])['status'] == 'pass'
    assert evaluate(spec, 'No proof of purchase is needed. Returns accepted for 90 days.', [])['status'] == 'fail'

def test_alternatives_are_bounded():
    with pytest.raises(ValueError):
        ExperimentSpec(acceptable_facts=[[]])
