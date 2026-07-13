"""tools.ner package.

Library:
    from tools.ner import extract_entities, Entity
"""
from .core import extract_entities
from .entity_schema import Entity

__all__ = ["extract_entities", "Entity"]
