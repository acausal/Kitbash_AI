"""Dataclasses for tools.filesystem_access (see SPEC-filesystem_access_v1.md).

Mirror the JSON shapes. Core functions build plain dicts (composability); these
document the contract. All timestamps are ISO-8601 UTC strings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FileInfo:
    size_bytes: int
    modification_time: str  # ISO 8601
    creation_time: Optional[str] = None
    is_file: bool = False
    is_directory: bool = False
    is_symlink: bool = False


@dataclass
class DirectoryEntry:
    name: str
    type: str  # "file" or "directory"
    size_bytes: Optional[int] = None
    modification_time: Optional[str] = None


@dataclass
class ReadResult:
    operation: str
    path: str
    status: str
    file_info: FileInfo
    content: str
    encoding: str = "utf-8"


@dataclass
class WriteResult:
    operation: str
    path: str
    mode: str
    status: str
    bytes_written: int
    atomic_write: bool
    file_info: FileInfo


@dataclass
class DeleteResult:
    operation: str
    path: str
    status: str
    deleted: bool
    file_info: Optional[FileInfo] = None


@dataclass
class ListResult:
    operation: str
    path: str
    recursive: bool
    status: str
    file_count: int
    directory_count: int
    contents: List[DirectoryEntry] = field(default_factory=list)


@dataclass
class ExistsResult:
    operation: str
    path: str
    status: str
    exists: bool
    is_file: bool
    is_directory: bool
    size_bytes: Optional[int] = None


@dataclass
class MetadataResult:
    operation: str
    path: str
    status: str
    metadata: FileInfo
