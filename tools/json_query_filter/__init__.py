"""tools.json_query_filter package.

Library (functions return JSON-serializable dicts):
    from tools.json_query_filter import (
        query_json, filter_json_array, extract_fields, flatten_json, validate_schema,
    )
"""
from .core import (
    extract_fields,
    filter_json_array,
    flatten_json,
    query_json,
    validate_schema,
)
from .query_schema import (
    ExtractionResult,
    FilterResult,
    FlattenResult,
    QueryResult,
    SchemaError,
    TypeCheck,
    ValidationResult,
)

__all__ = [
    "query_json", "filter_json_array", "extract_fields",
    "flatten_json", "validate_schema",
    "QueryResult", "FilterResult", "ExtractionResult", "FlattenResult",
    "TypeCheck", "SchemaError", "ValidationResult",
]
