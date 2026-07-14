"""tools.structured_validator package.

Library:
    from tools.structured_validator import validate_input, ParseResult
"""
from .core import validate_input
from .parse_result_schema import ParseResult

__all__ = ["validate_input", "ParseResult"]
