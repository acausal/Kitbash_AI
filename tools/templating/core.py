"""tools.templating core (stdlib only).

Variable substitution via string.Template. Strict by default (fail on missing
variable); optional lenient mode leaves placeholders intact. See
SPEC-templating_v1.md.
"""
import json
from string import Template
from typing import Any, Dict


def _serialize(value: Any) -> str:
    """Stringify a variable value per SPEC: str for str/bool/number, JSON else."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value)


def template_render(template: str, variables: Dict[str, Any] = None,
                    mode: str = "strict") -> Dict[str, Any]:
    """Render `template` with `variables`. Returns result/error dict (never raises)."""
    variables = variables or {}
    if not isinstance(template, str):
        return {"status": "error", "reason": "template must be a string", "template": template}
    safe = {k: _serialize(v) for k, v in variables.items()}
    try:
        tmpl = Template(template)
    except ValueError as e:
        return {"status": "error", "reason": f"Invalid template syntax: {e}", "template": template}
    if mode == "lenient":
        result = tmpl.safe_substitute(safe)
        return {
            "status": "success", "result": result,
            "variables_used": list(variables.keys()), "variables_missing": [],
            "template_length": len(template), "result_length": len(result),
        }
    try:
        result = tmpl.substitute(safe)
    except KeyError as e:
        missing = [str(e).strip("'\"")]
        return {
            "status": "error",
            "reason": f"Missing required variable: '{missing[0]}'",
            "missing_variables": missing,
        }
    except ValueError as e:
        return {"status": "error", "reason": f"Invalid template syntax: {e}", "template": template}
    return {
        "status": "success", "result": result,
        "variables_used": list(variables.keys()), "variables_missing": [],
        "template_length": len(template), "result_length": len(result),
    }


def extract_variables(template: str) -> list:
    """Return unique $variable names referenced by `template` (for logging/debug)."""
    import re
    return sorted(set(re.findall(r"\$(?!\$)\{?(\w+)\}?", template)))
