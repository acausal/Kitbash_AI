# filesystem_access

Safe, **Airlock-bounded** filesystem I/O for the tools ecosystem. All file
operations flow through strict path validation: rejects absolute paths, path
traversal, symlinks, and writes to protected directories (e.g. `cartridges/`).
Stdlib only (`os`, `pathlib`, `json`, `tempfile`). Isolation-first.

## Library

```python
from tools.filesystem_access import read_file, write_file, delete_file, \
    list_directory, file_exists, get_file_metadata

# config: dict with workspace_root + allowed_paths; None -> bundled default
cfg = {
    "workspace_root": "/abs/path/to/root",
    "allowed_paths": {
        "workspace/":   {"read": True,  "write": True,  "delete": True},
        "scratch/":     {"read": True,  "write": True,  "delete": True},
        "inbox/trusted/":{"read": True, "write": False, "delete": False},
        "inbox/external/":{"read": True,"write": True,  "delete": True},  # quarantine
        "outbox/":      {"read": True,  "write": True,  "delete": True},
        "cartridges/":  {"read": True,  "write": False, "delete": False},  # read-only
    },
}
r   = read_file("workspace/data.json", config=cfg)
w   = write_file("workspace/out.json", '{"k":1}', mode="w", config=cfg)  # atomic
d   = delete_file("scratch/tmp.json", config=cfg)
lst = list_directory("workspace/", recursive=False, config=cfg)
ex  = file_exists("workspace/data.json", config=cfg)
m   = get_file_metadata("workspace/data.json", config=cfg)
```

Every function returns a **plain JSON-serializable dict**.

### Boundaries enforced (all raise `ValueError` → CLI exit 1)
- Absolute paths (`/etc/passwd`) → rejected
- Traversal (`workspace/../../etc/passwd`) → resolved-outside-root rejected
- Symlinks → rejected
- Path not under an `allowed_paths` prefix → rejected
- Operation w/o permission (`write`/`delete` on `cartridges/`) → rejected

### Atomic writes
`write_file` writes to a sibling temp file (same dir → `fsync` → `os.replace`)
so a crash mid-write never leaves a partial file. Append (`mode="a"`) reads the
existing content, concatenates, then performs the same atomic replace.

### Audit trail
Every operation appends a JSONL entry to `config['audit_log_path']` (best-effort;
audit failure never breaks the operation).

## CLI

All subcommands print JSON to stdout; `write_file` reads content from stdin
(JSON string or raw text):

```bash
python -m tools.filesystem_access read_file --path "workspace/data.json"
echo '{"key":"value"}' | python -m tools.filesystem_access write_file --path "workspace/output.json"
echo "new line" | python -m tools.filesystem_access write_file --path "workspace/log.txt" --mode a
python -m tools.filesystem_access delete_file --path "scratch/temp.json"
python -m tools.filesystem_access list_directory --path "workspace/" [--recursive] [--no_metadata]
python -m tools.filesystem_access file_exists --path "workspace/data.json"
python -m tools.filesystem_access get_file_metadata --path "workspace/data.json"
# custom config:
python -m tools.filesystem_access read_file --path "workspace/data.json" --config /path/to/config.json
```

**Exit codes:** `0` success · `1` `ValueError` (boundary violation) ·
`2` `FileNotFoundError` · `3` `IOError`/`RuntimeError` (internal).

## Config

`load_config(path=None)` resolves (in order): `$KITBASH_CARTRIDGES_CONFIG` env,
`<cwd>/cartridges/filesystem_access_config.json` (SPEC canonical location),
or the bundled `tools/filesystem_access/default_config.json`. The canonical
`cartridges/` location is **not** written by this tool (it is a tracked,
sensitive directory); deploy a real config there if you want it used, otherwise
the bundled safe default applies. A malformed/unreadable config raises
`ValueError` at load time.

## Requirements

- Pure stdlib (`os`, `pathlib`, `json`, `tempfile`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.filesystem_access ...`
