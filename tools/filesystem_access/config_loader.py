"""Config loading for tools.filesystem_access.

The SPEC names `cartridges/filesystem_access_config.json` as the canonical
default location. To avoid writing into the tracked/sensitive `cartridges/`
directory, this loader falls back to a bundled default shipped inside the
package (`default_config.json`). Resolution order for load_config(path=None):

  1. KITBASH_CARTRIDGES_CONFIG env var (absolute path)
  2. <cwd>/cartridges/filesystem_access_config.json   (deployed canonical)
  3. <package>/default_config.json                    (bundled safe default)

A malformed/unreadable config raises ValueError (init-time failure, per SPEC).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Canonical SPEC default location (relative to CWD / repo root)
_CANONICAL_REL = os.path.join("cartridges", "filesystem_access_config.json")

_this_dir = Path(__file__).resolve().parent
_BUNDLED_DEFAULT = _this_dir / "default_config.json"


def _default_search_paths() -> list:
    paths = []
    env = os.environ.get("KITBASH_CARTRIDGES_CONFIG")
    if env:
        paths.append(Path(env))
    paths.append(Path.cwd() / _CANONICAL_REL)
    paths.append(_BUNDLED_DEFAULT)
    return paths


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load a filesystem config dict.

    If `path` is given, load from there. Otherwise search the default locations
    (first that exists wins). Raises ValueError if none found or JSON invalid.
    """
    if path:
        candidates = [Path(path)]
    else:
        candidates = _default_search_paths()

    last_err: Optional[Exception] = None
    for cand in candidates:
        try:
            with open(cand, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict) or "allowed_paths" not in cfg:
                raise ValueError("config missing 'allowed_paths'")
            return cfg
        except FileNotFoundError:
            last_err = FileNotFoundError(f"config not found: {cand}")
            continue
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed config JSON at {cand}: {e}")
        except OSError as e:
            last_err = e
            continue

    if path:
        raise ValueError(f"config file not found or unreadable: {path}")
    raise ValueError(f"no filesystem_access config found (searched: "
                     f"{[str(p) for p in candidates]}); last error: {last_err}")
