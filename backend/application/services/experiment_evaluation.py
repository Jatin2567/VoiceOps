"""Deterministic task checks. These test supplied criteria, not semantic truth."""
import json
import re


def normalize(value):
    return " ".join(tokens(value))


def tokens(value):
    # Keep numeric boundaries, decimals and common written quantities intact.
    words = {"thirty": "30", "ninety": "90", "one": "1", "two": "2", "three": "3"}
    units = {"day": "days", "hour": "hours", "minute": "minutes", "unit": "units"}
    return [units.get(t, words.get(t, t)) for t in re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+", str(value).casefold())]


def contains_fact(response, fact):
    """Exact token sequences with conservative, clause-local negation checks.

    This is a literal checker, not semantic entailment. Explicit alternatives
    let the author accept equivalent wording without guessing synonyms.
    """
    target = tokens(fact)
    if not target:
        return False
    for clause in re.split(r"(?<!\d)\.|\.(?!\d)|[!?;\n]|\b(?:but|however)\b", response.casefold()):
        source = tokens(clause)
        for i in range(len(source) - len(target) + 1):
            if source[i:i + len(target)] != target:
                continue
            nearby = source[max(0, i - 5):i] + source[i + len(target):i + len(target) + 3]
            negated = any(t in {"no", "not", "never", "without", "cannot", "isn", "doesn", "don", "won"} for t in nearby)
            if not negated or any(t in {"no", "not", "never", "without", "cannot"} for t in target):
                return True
    return False


def evaluate(spec, response, tools):
    checks = []
    def check(name, passed, expected):
        checks.append({"check": name, "passed": bool(passed), "expected": expected})
    for fact in spec.required_facts:
        check("required fact", contains_fact(response, fact), fact)
    for alternatives in spec.acceptable_facts:
        check("acceptable fact", any(contains_fact(response, fact) for fact in alternatives), alternatives)
    for fact in spec.forbidden_facts:
        check("forbidden fact absent", not contains_fact(response, fact), fact)
    if spec.expected_phrase:
        check("expected phrase", spec.expected_phrase.casefold() in response.casefold(), spec.expected_phrase)
    if spec.expected_fields:
        try:
            candidate = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            fields = json.loads(candidate)
            if not isinstance(fields, dict):
                fields = {}
        except (json.JSONDecodeError, TypeError):
            fields = {}
        for key, value in spec.expected_fields.items():
            check("field: " + key, key in fields and normalize(fields[key]) == normalize(value), value)
    if spec.expected_action or spec.expected_amount is not None or spec.expected_tool_status:
        # All supplied tool criteria must match the SAME call.
        matched = any((not spec.expected_action or t.get("action") == spec.expected_action)
            and (spec.expected_amount is None or t.get("amount") == spec.expected_amount)
            and (not spec.expected_tool_status or t.get("status") == spec.expected_tool_status)
            for t in tools)
        check("tool outcome", matched, {"action": spec.expected_action, "amount": spec.expected_amount,
                                       "status": spec.expected_tool_status})
    return {"status": "pass" if checks and all(c["passed"] for c in checks) else "fail" if checks else "unscored",
            "checks": checks, "scope": "Deterministic supplied criteria; semantic quality requires review."}
