"""tools.templating package.

Library:
    from tools.templating import template_render
    template_render("Hello $name", {"name": "Alice"})  # -> {"status":"success","result":"Hello Alice",...}

CLI:
    python -m tools.templating render "Hello $name" '{"name":"Alice"}'
    python -m tools.templating render-file template.txt vars.json --mode lenient

Safe string.Template substitution. Strict mode (default) errors on missing
variables; lenient mode leaves $placeholders intact. $$ -> literal $. Values
serialized via str()/json per SPEC. Errors returned as dicts, never raised.
Pure stdlib.
"""
from .core import template_render, extract_variables

__all__ = ["template_render", "extract_variables"]
