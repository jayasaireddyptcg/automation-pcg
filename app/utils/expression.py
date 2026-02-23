"""
Expression engine for variable interpolation.
Supports: {{trigger.body.email}}, {{node1.output.result}}, {{workflow.variables.user_id}}
"""

import re
from typing import Any


EXPRESSION_PATTERN = re.compile(r"\{\{(.+?)\}\}")


def resolve_expression(expression: str, context: dict[str, Any]) -> Any:
    """Resolve a single expression like 'trigger.body.email' against context."""
    parts = expression.strip().split(".")
    current = context
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def interpolate(template: Any, context: dict[str, Any]) -> Any:
    """
    Interpolate expressions in a template string or dict.
    If the entire string is a single expression, return the resolved value directly.
    Otherwise, replace all expressions with their string representations.
    """
    if isinstance(template, str):
        # Check if the entire string is a single expression
        match = EXPRESSION_PATTERN.fullmatch(template)
        if match:
            return resolve_expression(match.group(1), context)

        # Replace all expressions in the string
        def replacer(m: re.Match) -> str:
            val = resolve_expression(m.group(1), context)
            return str(val) if val is not None else ""

        return EXPRESSION_PATTERN.sub(replacer, template)

    elif isinstance(template, dict):
        return {k: interpolate(v, context) for k, v in template.items()}

    elif isinstance(template, list):
        return [interpolate(item, context) for item in template]

    return template
