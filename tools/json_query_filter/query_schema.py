"""Dataclasses for tools.json_query_filter (see SPEC-json_query_filter_v1.md).

These mirror the JSON shapes. Core functions build plain dicts (per the SPEC's
composability requirement); dataclasses document the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class QueryResult:
    query: str
    result: Any
    result_type: str  # "string", "number", "object", "array", "null", "boolean"
    found: bool
    result_count: Optional[int] = None


@dataclass
class FilterResult:
    filter: str
    total_items: int
    filtered_items: int
    results: List[Any]


@dataclass
class ExtractionResult:
    fields_requested: List[str]
    total_items: Optional[int] = None
    results: Union[Dict[str, Any], List[Dict[str, Any]]] = None
    extraction: Optional[Dict[str, Any]] = None


@dataclass
class FlattenResult:
    original: Dict[str, Any]
    flattened: Dict[str, Any]
    max_depth: Optional[int] = None
    separator: str = "."


@dataclass
class TypeCheck:
    expected: str
    actual: str
    match: bool


@dataclass
class SchemaError:
    field: str
    error: str


@dataclass
class ValidationResult:
    valid: bool
    schema_checks: Dict[str, Any]
    errors: List[SchemaError]
