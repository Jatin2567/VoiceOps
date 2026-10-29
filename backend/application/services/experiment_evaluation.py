"""Deterministic task checks. These test supplied criteria, not semantic truth."""
import json
import re


def normalize(value):
    return " ".join(re.findall(r"\w+", str(value).casefold()))


def evaluate(spec, response, tools):
    checks = []
    text = normalize(response)
    def check(name, passed, expected):
        checks.append({"check": name, "passed": bool(passed), "expected": expected})
    for fact in spec.required_facts:
        check("required fact", normalize(fact) in text, fact)
    for fact in spec.forbidden_facts:
        check("forbidden fact absent", normalize(fact) not in text, fact)
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
