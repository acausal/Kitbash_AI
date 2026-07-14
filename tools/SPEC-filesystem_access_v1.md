# SPEC: Filesystem Access v1

**Module:** `tools/filesystem_access/`  
**Status:** Ready for build  
**Dependencies:** stdlib (os, pathlib, json)  
**Priority:** Critical (safety-critical infrastructure; enforces Airlock boundaries; unblocks all I/O-heavy tools)

---

## Overview

Provide safe filesystem access for tools via strict path validation and trust boundary enforcement. All file I/O in the tools ecosystem flows through this tool. Implements the Airlock architecture: enforces allowed paths, rejects writes to protected directories, prevents symlink escape, prevents path traversal.

**Design principle:** Trust boundaries are explicit and enforced at every operation. Fail-loud on boundary violations.

**Use case:** "Tool needs to read configuration from workspace/, write results to scratch/, but is forbidden from touching cartridges/ or escaping the sandbox."

---

## Scope

### In Scope ✓
- Read files (full content)
- Write files (create, overwrite, append)
- List directories (non-recursive enumeration)
- Delete files
- Check file existence and metadata (size, modification time)
- Get directory listing with file info
- Atomic writes (temp → rename pattern for safety)
- Path normalization and validation
- Symlink detection (reject)
- Directory traversal prevention (reject `../`, etc.)
- Configurable allowed paths (via configuration file)
- Enforce read-only paths (e.g., cartridges/)
- Enforce quarantine paths (inbox/external → workspace one-way gate)
- Audit logging (every operation logged)

### Out of Scope ✗
- Recursive directory operations (enumerate first, then decide)
- File permissions/chmod (assume trusted user)
- Large file handling (streaming, chunking) — v1 reads entire file
- Symbolic link creation (reject all symlink operations)
- Hard links or special files
- File compression or encoding
- Atomic directory operations
- Cross-filesystem moves

---

## Module Structure

```
tools/filesystem_access/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  path_validator.py              # Airlock boundary enforcement
  config_loader.py               # load allowed paths from config
  cli.py                         # argparse CLI
  fs_schema.py                   # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## Configuration

### Config File Location

`cartridges/filesystem_access_config.json` (read-only from user perspective)

Example:
```json
{
  "workspace_root": "/home/user/kitbash/workspace_root",
  "allowed_paths": {
    "workspace/": {
      "read": true,
      "write": true,
      "delete": true,
      "promote_from": []
    },
    "scratch/": {
      "read": true,
      "write": true,
      "delete": true,
      "promote_from": []
    },
    "inbox/trusted/": {
      "read": true,
      "write": false,
      "delete": false,
      "promote_from": []
    },
    "inbox/external/": {
      "read": true,
      "write": true,
      "delete": true,
      "promote_from": []
    },
    "outbox/": {
      "read": true,
      "write": true,
      "delete": true,
      "promote_from": []
    },
    "cartridges/": {
      "read": true,
      "write": false,
      "delete": false,
      "promote_from": []
    }
  },
  "rejected_operations": [
    "write_to_cartridges",
    "promote_external_to_workspace",
    "follow_symlinks",
    "path_traversal"
  ],
  "audit_log_path": "inbox/external/filesystem_audit.jsonl",
  "last_updated": "2026-07-14T14:30:45Z"
}
```

**User-configurable fields:**
- `workspace_root` — base directory for all operations
- `allowed_paths` — which directories are accessible (read/write/delete permissions per path)
- `audit_log_path` — where to write audit trail

---

## API

### Core Functions (in `core.py`)

#### 1. `read_file(path: str, config: dict = None) -> dict`

**Purpose:** Read file content (full content; no streaming).

**Input:**
- `path` (str): File path (relative to workspace_root, e.g., `"workspace/data.json"`)
- `config` (dict, optional): Filesystem config; if None, load from default location

**Output (JSON):**
```json
{
  "operation": "read_file",
  "path": "workspace/data.json",
  "status": "success",
  "file_info": {
    "size_bytes": 1024,
    "modification_time": "2026-07-14T12:30:45Z",
    "is_file": true
  },
  "content": "{ ... file content ... }",
  "encoding": "utf-8"
}
```

**Behavior:**
- Validate path (allowed to read, no traversal, no symlinks)
- Read entire file
- Return content + metadata

**Error handling:**
- `ValueError` if path validation fails (boundary violation, traversal, symlink)
- `FileNotFoundError` if file doesn't exist
- `IOError` if read fails (permission, encoding issues)

---

#### 2. `write_file(path: str, content: str, mode: str = "w", config: dict = None) -> dict`

**Purpose:** Write file content (create or overwrite).

**Input:**
- `path` (str): File path relative to workspace_root
- `content` (str): File content to write
- `mode` (str): Write mode: `"w"` (overwrite, default), `"a"` (append), `"x"` (exclusive create)
- `config` (dict, optional): Filesystem config

**Output (JSON):**
```json
{
  "operation": "write_file",
  "path": "workspace/output.json",
  "mode": "w",
  "status": "success",
  "bytes_written": 2048,
  "atomic_write": true,
  "file_info": {
    "size_bytes": 2048,
    "modification_time": "2026-07-14T14:30:45Z"
  }
}
```

**Behavior:**
- Validate path (allowed to write, no traversal, no symlinks, no write to protected dirs)
- Use atomic write pattern (write to temp file, rename)
- Return metadata

**Error handling:**
- `ValueError` if path validation fails (write to cartridges/ forbidden, etc.)
- `FileNotFoundError` if directory doesn't exist
- `IOError` if write fails

---

#### 3. `delete_file(path: str, config: dict = None) -> dict`

**Purpose:** Delete a file.

**Input:**
- `path` (str): File path to delete
- `config` (dict, optional): Filesystem config

**Output (JSON):**
```json
{
  "operation": "delete_file",
  "path": "scratch/temp_data.json",
  "status": "success",
  "deleted": true,
  "file_info": {
    "size_bytes": 512,
    "modification_time": "2026-07-14T14:30:45Z"
  }
}
```

**Behavior:**
- Validate path (allowed to delete, no traversal)
- Delete file
- Return confirmation + metadata

**Error handling:**
- `ValueError` if path validation fails
- `FileNotFoundError` if file doesn't exist

---

#### 4. `list_directory(path: str, recursive: bool = False, include_metadata: bool = True, config: dict = None) -> dict`

**Purpose:** List directory contents (non-recursive by default).

**Input:**
- `path` (str): Directory path (e.g., `"workspace/"`)
- `recursive` (bool): If True, enumerate all subdirs (default: False, only immediate children)
- `include_metadata` (bool): Include file size, modification time (default: True)
- `config` (dict, optional): Filesystem config

**Output (JSON):**
```json
{
  "operation": "list_directory",
  "path": "workspace/",
  "recursive": false,
  "status": "success",
  "file_count": 3,
  "directory_count": 1,
  "contents": [
    {
      "name": "data.json",
      "type": "file",
      "size_bytes": 1024,
      "modification_time": "2026-07-14T12:30:45Z"
    },
    {
      "name": "subdir/",
      "type": "directory"
    },
    {
      "name": "output.txt",
      "type": "file",
      "size_bytes": 512,
      "modification_time": "2026-07-14T14:00:00Z"
    }
  ]
}
```

**Behavior:**
- Validate path (allowed to read)
- Enumerate immediate children (or recursive if flag set)
- Return list + metadata
- Mark files and directories separately

**Error handling:**
- `ValueError` if path validation fails
- `FileNotFoundError` if directory doesn't exist

---

#### 5. `file_exists(path: str, config: dict = None) -> dict`

**Purpose:** Check if file/directory exists.

**Input:**
- `path` (str): File or directory path
- `config` (dict, optional): Filesystem config

**Output (JSON):**
```json
{
  "operation": "file_exists",
  "path": "workspace/data.json",
  "status": "success",
  "exists": true,
  "is_file": true,
  "is_directory": false,
  "size_bytes": 1024
}
```

---

#### 6. `get_file_metadata(path: str, config: dict = None) -> dict`

**Purpose:** Get file metadata (size, modification time, type).

**Input:**
- `path` (str): File path
- `config` (dict, optional): Filesystem config

**Output (JSON):**
```json
{
  "operation": "get_file_metadata",
  "path": "workspace/data.json",
  "status": "success",
  "metadata": {
    "size_bytes": 1024,
    "modification_time": "2026-07-14T12:30:45Z",
    "creation_time": "2026-07-10T08:00:00Z",
    "is_file": true,
    "is_directory": false,
    "is_symlink": false
  }
}
```

---

### Path Validation (in `path_validator.py`)

All paths go through validator before any operation:

```python
class PathValidator:
    def __init__(self, workspace_root: str, config: dict):
        self.workspace_root = pathlib.Path(workspace_root).resolve()
        self.config = config
    
    def validate_path(self, path: str, operation: str) -> pathlib.Path:
        """
        Validate path and operation against Airlock boundaries.
        
        Args:
            path: Relative path (e.g., "workspace/data.json")
            operation: "read", "write", "delete", "list"
        
        Returns:
            Resolved absolute Path if valid
        
        Raises:
            ValueError: On boundary violation, traversal, symlink, etc.
        """
        # 1. Reject absolute paths
        if pathlib.Path(path).is_absolute():
            raise ValueError("Absolute paths forbidden")
        
        # 2. Resolve path (catch ../../../escape attempts)
        resolved = (self.workspace_root / path).resolve()
        if not str(resolved).startswith(str(self.workspace_root)):
            raise ValueError("Path traversal detected (escaped workspace_root)")
        
        # 3. Reject symlinks
        if resolved.is_symlink():
            raise ValueError("Symlinks forbidden")
        
        # 4. Check allowed paths
        allowed_dir = self._find_allowed_dir(path)
        if not allowed_dir:
            raise ValueError(f"Path not in allowed directories: {path}")
        
        # 5. Check operation permission for this dir
        perms = self.config['allowed_paths'][allowed_dir]
        if operation == "read" and not perms['read']:
            raise ValueError(f"Read forbidden in {allowed_dir}")
        if operation == "write" and not perms['write']:
            raise ValueError(f"Write forbidden in {allowed_dir}")
        if operation == "delete" and not perms['delete']:
            raise ValueError(f"Delete forbidden in {allowed_dir}")
        
        # 6. Special case: one-way gate (external → workspace requires validation)
        if operation == "write" and "inbox/external/" in str(path):
            # External writes always allowed (quarantine zone)
            pass
        if operation == "read" and "inbox/external/" in str(path):
            # Reading external allowed (but data not yet in workspace)
            pass
        
        return resolved
    
    def _find_allowed_dir(self, path: str) -> str:
        """Find which allowed_path prefix this path matches."""
        for allowed in self.config['allowed_paths'].keys():
            if path.startswith(allowed):
                return allowed
        return None
```

---

### CLI Interface (in `cli.py`)

```bash
# Read file
python -m tools.filesystem_access read_file --path "workspace/data.json"

# Write file
echo '{"key": "value"}' | python -m tools.filesystem_access write_file --path "workspace/output.json"

# Append to file
echo "new line" | python -m tools.filesystem_access write_file --path "workspace/log.txt" --mode a

# Delete file
python -m tools.filesystem_access delete_file --path "scratch/temp.json"

# List directory
python -m tools.filesystem_access list_directory --path "workspace/"

# List recursively
python -m tools.filesystem_access list_directory --path "workspace/" --recursive

# Check existence
python -m tools.filesystem_access file_exists --path "workspace/data.json"

# Get metadata
python -m tools.filesystem_access get_file_metadata --path "workspace/data.json"

# With custom config
python -m tools.filesystem_access read_file --path "workspace/data.json" --config "cartridges/filesystem_access_config.json"
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → file not found (FileNotFoundError)
- `3` → internal error (IOError, RuntimeError)

---

### Schema (in `fs_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

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
    file_info: FileInfo

@dataclass
class ListResult:
    operation: str
    path: str
    recursive: bool
    status: str
    file_count: int
    directory_count: int
    contents: List[DirectoryEntry]

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
```

---

## Audit Trail

Every operation logged to `inbox/external/filesystem_audit.jsonl`:

```jsonl
{"timestamp": "2026-07-14T14:30:45Z", "operation": "read_file", "path": "workspace/data.json", "status": "success", "file_size": 1024}
{"timestamp": "2026-07-14T14:31:00Z", "operation": "write_file", "path": "workspace/output.json", "status": "success", "bytes_written": 2048}
{"timestamp": "2026-07-14T14:31:15Z", "operation": "delete_file", "path": "scratch/temp.json", "status": "success"}
{"timestamp": "2026-07-14T14:31:30Z", "operation": "read_file", "path": "inbox/external/feeds.json", "status": "success", "file_size": 5120}
{"timestamp": "2026-07-14T14:32:00Z", "operation": "write_file", "path": "cartridges/model.onnx", "status": "failed", "error": "Write forbidden in cartridges/"}
```

**Audit log policy:** Append-only; non-destructive; rotated monthly.

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — file or directory not found
- `ValueError` — path validation fails (boundary, traversal, symlink, operation not allowed)
- `IOError` — read/write/delete fails (permission, disk, encoding)
- `RuntimeError` — internal filesystem error

**Logging:**
- Use `structured_logger.get_event_logger("filesystem_access")`
- Events: `operation_started`, `operation_success`, `operation_failed`, `boundary_violation`, `traversal_attempt`, `symlink_detected`
- Metadata: path, operation, status, error details, user context

---

## Test Cases

### Happy Path (read_file)
1. Read existing file → content + metadata returned
2. Read small file (< 1KB) → works
3. Read large file (1MB+) → works
4. Read text file (UTF-8) → correct encoding

### Happy Path (write_file)
5. Write new file (mode="w") → file created
6. Overwrite existing file (mode="w") → file replaced
7. Append to existing file (mode="a") → content appended
8. Create exclusive file (mode="x") → fails if exists
9. Atomic write (temp → rename) → works

### Happy Path (delete_file)
10. Delete existing file → file removed
11. Delete confirmed in listing → file gone

### Happy Path (list_directory)
12. List workspace/ → files and dirs enumerated
13. List empty directory → empty contents array
14. Recursive listing → all subdirectory contents included
15. File metadata included → size, mtime present

### Happy Path (file_exists)
16. File exists → returns true
17. File doesn't exist → returns false
18. Directory exists → returns true

### Happy Path (get_file_metadata)
19. Get metadata for file → all fields populated
20. File size correct → matches actual

### Boundary Enforcement
21. Read from workspace/ → allowed
22. Write to workspace/ → allowed
23. Read from cartridges/ → allowed
24. Write to cartridges/ → `ValueError` (forbidden)
25. Delete from cartridges/ → `ValueError` (forbidden)
26. Read from inbox/trusted/ → allowed
27. Write to inbox/external/ → allowed (quarantine zone)
28. Read from inbox/external/ → allowed (but not auto-promoted to workspace)

### Edge Cases
29. Path with trailing slash: `workspace/` → treated consistently
30. Path with no leading slash: `workspace/data.json` → accepted
31. Empty file → readable, size=0
32. Very long filename (255+ chars) → handled
33. File with special characters in name → preserved
34. File with Unicode name → handled correctly
35. Concurrent operations (if applicable) → atomic write prevents corruption
36. Symlink to file → rejected (symlink detection)
37. Directory named like file: `workspace/data` (no extension) → works
38. Reading file that was just deleted → `FileNotFoundError`

### Error Cases
39. Absolute path: `/etc/passwd` → `ValueError`
40. Path traversal: `workspace/../../etc/passwd` → `ValueError`
41. Symlink: `workspace/link_to_data` (symlink) → `ValueError`
42. Write to cartridges/ → `ValueError`
43. Delete from read-only dir → `ValueError`
44. Non-existent directory: read `nonexistent/file.txt` → `FileNotFoundError`
45. Invalid operation: unknown mode in write → `ValueError`
46. Disk full (if simulated) → `IOError`
47. Path not in allowed_paths → `ValueError`
48. Malformed config → `ValueError` at init time
49. Permission denied (if filesystem enforces) → `IOError`
50. Invalid UTF-8 encoding → `IOError` (or log as warning, return raw bytes?)

### CLI Behavior
51. CLI exit code 0 on success
52. CLI exit code 1 on ValueError (boundary violation)
53. CLI exit code 2 on FileNotFoundError
54. CLI exit code 3 on IOError/RuntimeError
55. CLI reads config from default location if not specified
56. CLI with custom config path → loads from that path

---

## Non-Goals (Explicitly Out of Scope)

- Recursive directory deletion (must enumerate and delete files individually)
- File permissions/chmod (assume trusted user)
- Streaming large files (v1 reads entire file into memory)
- Symbolic link creation
- Hard links or special files
- File compression
- Cross-filesystem moves
- Atomic directory operations

---

## Implementation Notes

### Atomic Write Pattern

```python
def write_file(path: str, content: str, mode: str = "w"):
    """Write file atomically (temp → rename)."""
    resolved_path = validate_path(path, "write")
    
    # Write to temp file
    temp_path = resolved_path.with_suffix('.tmp')
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Atomic rename
    temp_path.replace(resolved_path)
    
    # Success
    return {"status": "success", "bytes_written": len(content.encode('utf-8'))}
```

### Path Resolution Strategy

Always resolve to absolute path, then check if within workspace_root:
```python
resolved = (workspace_root / relative_path).resolve()
if not str(resolved).startswith(str(workspace_root)):
    raise ValueError("Path traversal detected")
```

### Symlink Detection

Check for symlinks at every resolution step:
```python
if resolved.is_symlink():
    raise ValueError("Symlinks forbidden")
```

---

## Success Criteria

- ✅ All 56 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2, 3)
- ✅ Path validation enforces all Airlock boundaries
- ✅ Writes to protected dirs (cartridges/) rejected
- ✅ Path traversal attempts (`../`) rejected
- ✅ Symlinks rejected
- ✅ Atomic writes prevent partial/corrupted files
- ✅ Audit trail comprehensive and accurate
- ✅ Config loading works (default + custom paths)
- ✅ Edge cases handled gracefully
- ✅ Error messages clear and actionable
- ✅ Errors logged via structured_logger with context
- ✅ README documents all operations, boundaries, examples

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
