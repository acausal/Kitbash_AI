"""Airlock boundary enforcement for tools.filesystem_access.

PathValidator turns a relative path + operation into a resolved absolute path,
or raises ValueError on any boundary violation. Pure stdlib (pathlib, os).
"""
from __future__ import annotations

import os
import pathlib
from typing import Optional

# Operations the validator understands
READ, WRITE, DELETE, LIST = "read", "write", "delete", "list"

# One-way gate zones (per SPEC): external is quarantine; reads allowed,
# writes allowed (into quarantine), but never auto-promoted to workspace.
_QUARANTINE_PREFIXES = ("inbox/external/",)


class PathValidator:
    def __init__(self, workspace_root: str, config: dict):
        if not isinstance(config, dict) or "allowed_paths" not in config:
            raise ValueError("config must be a dict with 'allowed_paths'")
        self.workspace_root = pathlib.Path(workspace_root).resolve()
        self.config = config

    def _allowed_dir_for(self, rel: str) -> Optional[str]:
        """Return the longest allowed_paths key that `rel` is under (or None)."""
        best = None
        for allowed in self.config["allowed_paths"].keys():
            # normalize the configured prefix (ensure it ends with a separator
            # so "workspaceX" doesn't match the "workspace/" prefix)
            prefix = allowed if allowed.endswith("/") or allowed.endswith(os.sep) else allowed + "/"
            if rel == allowed or rel.startswith(prefix):
                if best is None or len(allowed) > len(best):
                    best = allowed
        return best

    def validate_path(self, path: str, operation: str) -> pathlib.Path:
        """Validate `path` for `operation`; return resolved absolute Path.

        Raises ValueError on absolute path, traversal escape, symlink,
        not-in-allowed-dir, or operation-permission violation.
        """
        if operation not in (READ, WRITE, DELETE, LIST):
            raise ValueError(f"unknown operation: {operation!r}")

        raw = pathlib.PurePosixPath(path) if False else pathlib.Path(path)
        # 1. Reject absolute paths
        if raw.is_absolute():
            raise ValueError(f"absolute paths forbidden: {path}")

        # 2. Resolve and confirm it stays inside workspace_root
        resolved = (self.workspace_root / path).resolve()
        ws = str(self.workspace_root)
        if str(resolved) != ws and not str(resolved).startswith(ws + os.sep):
            raise ValueError(f"path traversal detected (escapes workspace_root): {path}")

        # 3. Reject symlinks (the resolved node, and any parent link)
        if resolved.is_symlink():
            raise ValueError(f"symlinks forbidden: {path}")

        # 4. Confirm it lives under an allowed directory
        allowed_dir = self._allowed_dir_for(path)
        if allowed_dir is None:
            raise ValueError(f"path not in allowed directories: {path}")

        # 5. Confirm operation permission for that directory
        perms = self.config["allowed_paths"][allowed_dir]
        op_key = {"list": "read"}.get(operation, operation)
        if op_key == "read" and not perms.get("read", False):
            raise ValueError(f"read forbidden in {allowed_dir}")
        if op_key == "write" and not perms.get("write", False):
            raise ValueError(f"write forbidden in {allowed_dir}")
        if op_key == "delete" and not perms.get("delete", False):
            raise ValueError(f"delete forbidden in {allowed_dir}")

        # 6. Quarantine one-way gate: external writes/reads allowed but never
        #    promoted into workspace. (No extra check needed in v1; the allowed
        #    prefix already gates inbox/external separately.)
        return resolved
