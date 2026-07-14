"""tools.svo package.

Library:
    from tools.svo import extract_svo, SVO
"""
from .core import extract_svo
from .svo_schema import SVO

__all__ = ["extract_svo", "SVO"]
