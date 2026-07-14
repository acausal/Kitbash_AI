"""Dataclasses for tools.csv_operations (see SPEC-csv_operations_v1.md).

Mirror the JSON shapes. Core functions build plain dicts (composability); these
document the contract.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ColumnStats:
    type: str  # "text" | "numeric"
    unique_count: int
    sample_values: List[str]
    min: Optional[float] = None
    max: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"type": self.type, "unique_count": self.unique_count,
             "sample_values": self.sample_values}
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        return d


@dataclass
class ParseResult:
    operation: str
    row_count: int
    column_count: int
    has_header: bool
    delimiter: str
    headers: List[str]
    rows: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {"operation": self.operation, "row_count": self.row_count,
                "column_count": self.column_count, "has_header": self.has_header,
                "delimiter": self.delimiter, "headers": self.headers,
                "rows": self.rows}


@dataclass
class FilterResult:
    operation: str
    column: str
    operator: str
    value: str
    input_row_count: int
    output_row_count: int
    rows: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {"operation": self.operation, "column": self.column,
                "operator": self.operator, "value": self.value,
                "input_row_count": self.input_row_count,
                "output_row_count": self.output_row_count, "rows": self.rows}


@dataclass
class SelectResult:
    operation: str
    columns: List[str]
    exclude: bool
    input_column_count: int
    output_column_count: int
    rows: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {"operation": self.operation, "columns": self.columns,
                "exclude": self.exclude,
                "input_column_count": self.input_column_count,
                "output_column_count": self.output_column_count,
                "rows": self.rows}


@dataclass
class SortResult:
    operation: str
    column: str
    descending: bool
    numeric: bool
    rows: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {"operation": self.operation, "column": self.column,
                "descending": self.descending, "numeric": self.numeric,
                "rows": self.rows}


@dataclass
class UniqueResult:
    operation: str
    column: str
    total_rows: int
    unique_count: int
    values: List[str]
    value_counts: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {"operation": self.operation, "column": self.column,
                "total_rows": self.total_rows, "unique_count": self.unique_count,
                "values": self.values, "value_counts": self.value_counts}


@dataclass
class StatsResult:
    operation: str
    row_count: int
    column_count: int
    columns: Dict[str, ColumnStats]

    def to_dict(self) -> Dict[str, Any]:
        return {"operation": self.operation, "row_count": self.row_count,
                "column_count": self.column_count,
                "columns": {k: v.to_dict() for k, v in self.columns.items()}}
