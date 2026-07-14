"""tools.unicode_normalizer package.

Library:
    from tools.unicode_normalizer import normalize_text, normalize_file, detect_mojibake
"""
from .core import normalize_text, normalize_file, detect_mojibake
from .normalizer_schema import (
    NormalizeResult, FileResult, MojibakeResult, CharCount,
)

__all__ = [
    "normalize_text", "normalize_file", "detect_mojibake",
    "NormalizeResult", "FileResult", "MojibakeResult", "CharCount",
]
