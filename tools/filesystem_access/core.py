"""filesystem_access core: safe, Airlock-bounded file I/O.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib (os, pathlib,
json, tempfile, datetime, random, io) plus Kitbash core's structured_logger
(read-only helper; failed import is non-fatal) and the package's own
path_validator / config_loader. Consumes a config dict (or loads the bundled
default) that defines workspace_root + allowed_paths with per-dir read/write/
delete permissions.

Every function returns a **plain JSON-serializable dict**. Error taxonomy:
  ValueError        -> boundary/traversal/symlink/permission/invalid-input (CLI 1)
  FileNotFoundError -> file/dir missing                               (CLI 2)
  OSError/RuntimeError -> I/O / internal                              (CLI 3)
"""
from __future__ import annotations

import datetime
import io
import json
import os
import random
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from .config_loader import load_config
from .path_validator import PathValidator, READ, WRITE, DELETE, LIST

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("filesystem_access")
except Exception:
    _logger = None

_VALID_MODES = ("w", "a", "x")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _file_info(path: Path) -> Dict[str, Any]:
    st = path.stat()
    return {
        "size_bytes": st.st_size,
        "modification_time": _iso(st.st_mtime),
        "creation_time": _iso(st.st_ctime),
        "is_file": path.is_file(),
        "is_directory": path.is_dir(),
        "is_symlink": path.is_symlink(),
    }


def _resolve_config(config: Optional[Any]):
    """Accept a config dict, a path to a config file, or None (bundled default)."""
    if config is None:
        return load_config()
    if isinstance(config, dict):
        return config
    if isinstance(config, str):
        return load_config(config)  # load from the given path
    raise ValueError("config must be a dict, a path string, or None")


def _get_validator(config: Optional[Any]):
    cfg = _resolve_config(config)
    return PathValidator(cfg.get("workspace_root", "."), cfg), cfg


def _audit(cfg: dict, operation: str, path: str, status: str, **extra) -> None:
    """Append-only JSONL audit. Best-effort: never breaks the main operation."""
    try:
        ap = cfg.get("audit_log_path")
        if not ap:
            return
        root = Path(cfg.get("workspace_root", ".")).resolve()
        log_path = (root / ap).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": _now_iso(), "operation": operation,
                 "path": path, "status": status, **extra}
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        if _logger:
            try:
                _logger.log(event_type="audit_write_failed",
                            data={"error": traceback.format_exc(limit=2)})
            except Exception:
                pass


def _op_start(operation: str, path: str) -> None:
    if _logger:
        try:
            _logger.log(event_type="operation_started",
                        data={"operation": operation, "path": path})
        except Exception:
            pass


def _op_done(operation: str, path: str, status: str) -> None:
    if _logger:
        try:
            _logger.log(event_type="operation_success" if status == "success"
                        else "operation_failed",
                        data={"operation": operation, "path": path, "status": status})
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 1. read_file
# --------------------------------------------------------------------------- #
def read_file(path: str, config: Optional[dict] = None) -> dict:
    validator, cfg = _get_validator(config)
    _op_start("read_file", path)
    resolved = validator.validate_path(path, READ)
    if not resolved.exists():
        _audit(cfg, "read_file", path, "failed", error="not found")
        _op_done("read_file", path, "failed")
        raise FileNotFoundError(f"file not found: {path}")
    if resolved.is_dir():
        _audit(cfg, "read_file", path, "failed", error="is directory")
        _op_done("read_file", path, "failed")
        raise IOError(f"path is a directory, not a file: {path}")
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        _audit(cfg, "read_file", path, "failed", error="encoding")
        _op_done("read_file", path, "failed")
        raise IOError(f"file is not valid UTF-8: {path} ({e})")
    except OSError as e:
        _audit(cfg, "read_file", path, "failed", error=str(e))
        _op_done("read_file", path, "failed")
        raise IOError(f"read failed: {path} ({e})")
    result = {
        "operation": "read_file",
        "path": path,
        "status": "success",
        "file_info": _file_info(resolved),
        "content": content,
        "encoding": "utf-8",
    }
    _audit(cfg, "read_file", path, "success", file_size=len(content.encode("utf-8")))
    _op_done("read_file", path, "success")
    return result


# --------------------------------------------------------------------------- #
# 2. write_file (atomic)
# --------------------------------------------------------------------------- #
def write_file(path: str, content: str, mode: str = "w",
               config: Optional[dict] = None) -> dict:
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid write mode: {mode!r} (expected w/a/x)")
    validator, cfg = _get_validator(config)
    _op_start("write_file", path)
    resolved = validator.validate_path(path, WRITE)

    if mode == "x" and resolved.exists():
        _audit(cfg, "write_file", path, "failed", error="exists (exclusive)")
        _op_done("write_file", path, "failed")
        raise ValueError(f"file already exists, exclusive create rejected: {path}")

    # Compute final on-disk content
    if mode == "a" and resolved.exists():
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                existing = f.read()
        except (OSError, UnicodeDecodeError) as e:
            _audit(cfg, "write_file", path, "failed", error=str(e))
            _op_done("write_file", path, "failed")
            raise IOError(f"append read failed: {path} ({e})")
        final = existing + content
    else:
        final = content

    # Ensure parent directory exists
    parent = resolved.parent
    if not parent.exists():
        _audit(cfg, "write_file", path, "failed", error="parent dir missing")
        _op_done("write_file", path, "failed")
        raise FileNotFoundError(f"parent directory does not exist: {parent}")

    # Atomic write: temp in same dir -> fsync -> os.replace
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(parent), suffix=f".tmp.{os.getpid()}.{random.randint(0, 1 << 30)}")
        with os.fdopen(fd, "w", encoding="utf-8") as tf:
            tf.write(final)
            tf.flush()
            os.fsync(tf.fileno())
        os.replace(tmp_name, resolved)
    except OSError as e:
        _audit(cfg, "write_file", path, "failed", error=str(e))
        _op_done("write_file", path, "failed")
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass
        raise IOError(f"write failed: {path} ({e})")

    result = {
        "operation": "write_file",
        "path": path,
        "mode": mode,
        "status": "success",
        "bytes_written": len(content.encode("utf-8")),
        "atomic_write": True,
        "file_info": _file_info(resolved),
    }
    _audit(cfg, "write_file", path, "success", bytes_written=result["bytes_written"])
    _op_done("write_file", path, "success")
    return result


# --------------------------------------------------------------------------- #
# 3. delete_file
# --------------------------------------------------------------------------- #
def delete_file(path: str, config: Optional[dict] = None) -> dict:
    validator, cfg = _get_validator(config)
    _op_start("delete_file", path)
    resolved = validator.validate_path(path, DELETE)
    if not resolved.exists():
        _audit(cfg, "delete_file", path, "failed", error="not found")
        _op_done("delete_file", path, "failed")
        raise FileNotFoundError(f"file not found: {path}")
    info = _file_info(resolved)
    try:
        if resolved.is_dir():
            raise IOError(f"path is a directory, not a file: {path}")
        os.remove(resolved)
    except OSError as e:
        _audit(cfg, "delete_file", path, "failed", error=str(e))
        _op_done("delete_file", path, "failed")
        raise IOError(f"delete failed: {path} ({e})")
    result = {
        "operation": "delete_file",
        "path": path,
        "status": "success",
        "deleted": True,
        "file_info": info,
    }
    _audit(cfg, "delete_file", path, "success")
    _op_done("delete_file", path, "success")
    return result


# --------------------------------------------------------------------------- #
# 4. list_directory
# --------------------------------------------------------------------------- #
def list_directory(path: str, recursive: bool = False,
                   include_metadata: bool = True,
                   config: Optional[dict] = None) -> dict:
    validator, cfg = _get_validator(config)
    _op_start("list_directory", path)
    resolved = validator.validate_path(path, LIST)
    if not resolved.exists():
        _audit(cfg, "list_directory", path, "failed", error="not found")
        _op_done("list_directory", path, "failed")
        raise FileNotFoundError(f"directory not found: {path}")
    if not resolved.is_dir():
        _audit(cfg, "list_directory", path, "failed", error="not a directory")
        _op_done("list_directory", path, "failed")
        raise IOError(f"path is not a directory: {path}")

    if recursive:
        entries = [p for p in resolved.rglob("*")]
    else:
        entries = list(resolved.iterdir())

    contents = []
    file_count = dir_count = 0
    for p in entries:
        is_dir = p.is_dir()
        name = p.name + ("/" if is_dir else "")
        entry: Dict[str, Any] = {"name": name, "type": "directory" if is_dir else "file"}
        if include_metadata:
            st = p.stat()
            entry["size_bytes"] = st.st_size
            entry["modification_time"] = _iso(st.st_mtime)
        contents.append(entry)
        if is_dir:
            dir_count += 1
        else:
            file_count += 1

    result = {
        "operation": "list_directory",
        "path": path,
        "recursive": recursive,
        "status": "success",
        "file_count": file_count,
        "directory_count": dir_count,
        "contents": contents,
    }
    _audit(cfg, "list_directory", path, "success", file_count=file_count)
    _op_done("list_directory", path, "success")
    return result


# --------------------------------------------------------------------------- #
# 5. file_exists
# --------------------------------------------------------------------------- #
def file_exists(path: str, config: Optional[dict] = None) -> dict:
    validator, cfg = _get_validator(config)
    _op_start("file_exists", path)
    resolved = validator.validate_path(path, READ)
    exists = resolved.exists()
    result: Dict[str, Any] = {
        "operation": "file_exists",
        "path": path,
        "status": "success",
        "exists": exists,
        "is_file": resolved.is_file() if exists else False,
        "is_directory": resolved.is_dir() if exists else False,
    }
    if exists and resolved.is_file():
        result["size_bytes"] = resolved.stat().st_size
    _audit(cfg, "file_exists", path, "success", exists=exists)
    _op_done("file_exists", path, "success")
    return result


# --------------------------------------------------------------------------- #
# 6. get_file_metadata
# --------------------------------------------------------------------------- #
def get_file_metadata(path: str, config: Optional[dict] = None) -> dict:
    validator, cfg = _get_validator(config)
    _op_start("get_file_metadata", path)
    resolved = validator.validate_path(path, READ)
    if not resolved.exists():
        _audit(cfg, "get_file_metadata", path, "failed", error="not found")
        _op_done("get_file_metadata", path, "failed")
        raise FileNotFoundError(f"file not found: {path}")
    result = {
        "operation": "get_file_metadata",
        "path": path,
        "status": "success",
        "metadata": _file_info(resolved),
    }
    _audit(cfg, "get_file_metadata", path, "success")
    _op_done("get_file_metadata", path, "success")
    return result
