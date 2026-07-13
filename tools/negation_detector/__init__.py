"""tools.negation_detector package.

Library:
    from tools.negation_detector import detect_negations, Token
"""
from .core import detect_negations
from .token_schema import Token

__all__ = ["detect_negations", "Token"]
