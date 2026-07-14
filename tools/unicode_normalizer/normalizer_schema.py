"""Dataclasses for tools.unicode_normalizer (see SPEC-unicode_normalizer_v1.md).

Mirror the JSON shapes. Core functions build plain dicts (composability); these
document the contract.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class CharCount:
    original: int
    normalized: int

    def to_dict(self) -> Dict[str, int]:
        return {"original": self.original, "normalized": self.normalized}


@dataclass
class NormalizeResult:
    operation: str
    original: str
    normalized: str
    changed: bool
    char_count: CharCount
    mojibake_detected: bool
    script_types_detected: List[str]
    preserve_unknown_mode: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "original": self.original,
            "normalized": self.normalized,
            "changed": self.changed,
            "char_count": self.char_count.to_dict(),
            "mojibake_detected": self.mojibake_detected,
            "script_types_detected": self.script_types_detected,
            "preserve_unknown_mode": self.preserve_unknown_mode,
        }


@dataclass
class FileResult:
    operation: str
    input_path: str
    output_path: str
    bytes_read: int
    bytes_written: int
    lines_processed: int
    normalized: bool
    mojibake_detected: bool
    script_types_detected: List[str]
    processing_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "bytes_read": self.bytes_read,
            "bytes_written": self.bytes_written,
            "lines_processed": self.lines_processed,
            "normalized": self.normalized,
            "mojibake_detected": self.mojibake_detected,
            "script_types_detected": self.script_types_detected,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class MojibakeResult:
    operation: str
    original: str
    mojibake_detected: bool
    confidence: float
    likely_source_encoding: Optional[str]
    analysis: Dict[str, bool]
    suggested_fix: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "original": self.original,
            "mojibake_detected": self.mojibake_detected,
            "confidence": self.confidence,
            "likely_source_encoding": self.likely_source_encoding,
            "analysis": self.analysis,
            "suggested_fix": self.suggested_fix,
        }
