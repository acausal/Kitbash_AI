"""tools.diff_patch package.

Library:
    from tools.diff_patch import diff_generate, diff_apply
    diff_generate("hello\\nworld", "hello\\nWORLD")   # -> {"status":"success","diff":"...",...}
    diff_apply(text, patch)                            # -> {"status":"success","result":...,...}

CLI:
    python -m tools.diff_patch generate a.txt b.txt --context 1
    python -m tools.diff_patch apply orig.txt patch.unified

Generate uses difflib.unified_diff; apply parses hunks and applies with 1-line
fuzz tolerance. Binary (null-byte) input errors. Errors returned as dicts,
never raised. Pure stdlib.
"""
from .core import diff_generate, diff_apply

__all__ = ["diff_generate", "diff_apply"]
