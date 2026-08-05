"""Evaluate canonical executable-zoning JSON without importing declarations."""

from __future__ import annotations

from math import isfinite


def predicate_matches(predicate: dict, context: dict) -> bool:
    actual = context.get(predicate["field"])
    if predicate["operator"] == "eq":
        return actual == predicate["value"]
    if predicate["operator"] == "in":
        return actual in predicate["value"]
    if predicate["operator"] == "<":
        return actual is not None and actual < predicate["value"]
    if predicate["operator"] == ">=":
        return actual is not None and actual >= predicate["value"]
    if predicate["operator"] == "<=":
        return actual is not None and actual <= predicate["value"]
    if predicate["operator"] == ">":
        return actual is not None and actual > predicate["value"]
    raise ValueError(f"unsupported predicate operator: {predicate['operator']}")


def applicable_rules(package: dict, context: dict) -> list[dict]:
    return [
        rule for rule in package["rules"]
        if all(predicate_matches(item, context) for item in rule["when"]["all"])
    ]


def evaluate_permissions(package: dict, context: dict) -> list[dict]:
    """Evaluate use/district permissions without inventing missing branch facts."""
    results = []
    for permission in package.get("permissions", []):
        if permission["use"] != context.get("use"):
            continue
        if permission["district"] != context.get("district"):
            continue
        predicates = permission.get("when", {}).get("all", ())
        missing = sorted({
            item["field"] for item in predicates if item["field"] not in context
        })
        if missing:
            status = "unknown"
        elif all(predicate_matches(item, context) for item in predicates):
            status = "applicable"
        else:
            status = "not_applicable"
        results.append({
            "permissionId": permission["id"],
            "status": status,
            "permission": permission["permission"] if status == "applicable" else None,
            "missingContext": missing,
            "conditions": permission["conditions"],
            "source": permission["source"],
        })
    return results


def evaluate_package(package: dict, context: dict, measurements: dict) -> list[dict]:
    results = []
    for rule in applicable_rules(package, context):
        requirement = rule["requirement"]
        raw = measurements.get(requirement["metric"])
        try:
            measured = float(raw)
        except (TypeError, ValueError):
            measured = float("nan")
        if not isfinite(measured):
            status = "unknown"
            measured_value = None
        elif requirement["operator"] in {">=", "<=", "=="}:
            status = _compare(measured, requirement["operator"], requirement["value"])
            measured_value = measured
        else:
            raise ValueError(
                f"unsupported requirement operator: {requirement['operator']}"
            )
        results.append({
            "ruleId": rule["id"],
            "status": status,
            "measuredValue": measured_value,
            "requirement": requirement,
            "source": rule["source"],
            "exceptionsNotEvaluated": rule["exceptions"],
        })
    formulas = {item["id"]: item for item in package.get("formulas", [])}
    for rule in package.get("computedRules", []):
        if not all(predicate_matches(item, context) for item in rule["when"]["all"]):
            continue
        formula = formulas[rule["formula"]]
        formula_inputs = {**context, **measurements}
        required = _evaluate_expression(formula["expression"], formula_inputs)
        if required is not None and formula.get("minimum") is not None:
            required = max(required, formula["minimum"])
        raw = measurements.get(rule["metric"])
        try:
            measured = float(raw)
        except (TypeError, ValueError):
            measured = float("nan")
        if required is None or not isfinite(measured):
            status, measured_value = "unknown", None if not isfinite(measured) else measured
        else:
            status = _compare(measured, rule["operator"], required)
            measured_value = measured
        results.append({
            "ruleId": rule["id"],
            "status": status,
            "measuredValue": measured_value,
            "requirement": {
                "metric": rule["metric"], "operator": rule["operator"],
                "value": required, "unit": formula["output_unit"],
                "formula": formula["id"],
            },
            "source": rule["source"],
            "exceptionsNotEvaluated": rule["exceptions"],
        })
    return results


def _compare(measured: float, operator: str, required: float) -> str:
    if operator == ">=":
        return "meets" if measured >= required else "fails"
    if operator == "<=":
        return "meets" if measured <= required else "fails"
    if operator == "==":
        return "meets" if measured == required else "fails"
    raise ValueError(f"unsupported requirement operator: {operator}")


def _evaluate_expression(expression, measurements: dict) -> float | None:
    if isinstance(expression, (int, float)):
        return float(expression)
    if "var" in expression:
        try:
            value = float(measurements.get(expression["var"]))
        except (TypeError, ValueError):
            return None
        return value if isfinite(value) else None
    values = [_evaluate_expression(item, measurements) for item in expression["args"]]
    if any(value is None for value in values):
        return None
    if expression["op"] == "add":
        return sum(values)
    if expression["op"] == "multiply":
        result = 1.0
        for value in values:
            result *= value
        return result
    if expression["op"] == "divide":
        return values[0] / values[1]
    if expression["op"] == "subtract":
        return values[0] - values[1]
    if expression["op"] == "min":
        return min(values)
    if expression["op"] == "max":
        return max(values)
    raise ValueError(f"unsupported expression operator: {expression['op']}")
