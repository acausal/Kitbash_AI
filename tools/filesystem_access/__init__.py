"""tools.filesystem_access package.

Library (functions return JSON-serializable dicts):
    from tools.filesystem_access import (
        read_file, write_file, delete_file,
        list_directory, file_exists, get_file_metadata,
    )
"""
from .core import (
    delete_file, file_exists, get_file_metadata,
    list_directory, read_file, write_file,
)
from .config_loader import load_config
from .path_validator import PathValidator
from .fs_schema import (
    DeleteResult, DirectoryEntry, ExistsResult, FileInfo,
    ListResult, MetadataResult, ReadResult, WriteResult,
)

__all__ = [
    "read_file", "write_file", "delete_file",
    "list_directory", "file_exists", "get_file_metadata",
    "load_config", "PathValidator",
    "FileInfo", "DirectoryEntry", "ReadResult", "WriteResult",
    "DeleteResult", "ListResult", "ExistsResult", "MetadataResult",
]
