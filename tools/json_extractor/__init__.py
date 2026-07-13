"""json_extractor: JSON -> text from known fields (stdlib json).

Isolation-first tool (see tools/README.md). Allowed: stdlib + optional
structured_logger. No orchestrator/sleep_*/redis_*/engine/mtr_*.
"""
from __future__ import annotations
import os, sys, json

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("json_extractor")
except Exception:
    _logger = None

_FIELDS = ("content", "text", "body", "message", "data")
_SEP = "\n---\n"


def convert_json_to_markdown(input_path: str, output_path: str) -> None:
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"input file not found: {input_path}")
    if not input_path.lower().endswith(".json"):
        raise ValueError(f"input is not a .json file: {input_path}")

    if _logger:
        _logger.log(event_type="extraction_started", data={"source": input_path})

    try:
        with open(input_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON parse error: {e}") from e
    except UnicodeDecodeError as e:
        raise RuntimeError(f"JSON encoding error: {e}") from e
    except OSError as e:
        raise IOError(f"cannot read input {input_path}: {e}") from e

    text = _extract(data)
    if text is None:
        raise ValueError("No extractable text field found "
                         "(expected one of: content, text, body, message, data)")
    text = _normalize(text)  # empty allowed if a field was present
    _write(text, input_path, output_path)


def _extract(data) -> "str | None":
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        parts = [p for p in (_extract(item) for item in data) if p]
        return _SEP.join(parts) if parts else None
    if isinstance(data, dict):
        hits = []
        for fld in _FIELDS:
            if fld in data and isinstance(data[fld], str) and data[fld].strip():
                hits.append(data[fld])
        return _SEP.join(hits) if hits else None
    # scalar/other: nothing extractable
    return None


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    out = "\n".join(lines)
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip() + "\n" if out.strip() else ""


def _write(text: str, input_path: str, output_path: str) -> None:
    out_dir = os.path.dirname(os.path.abspath(output_path))
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        raise IOError(f"cannot create output directory {out_dir}: {e}") from e
    try:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as e:
        raise IOError(f"cannot write output {output_path}: {e}") from e
    if _logger:
        _logger.log(event_type="extraction_complete",
                    data={"source": input_path, "dest": output_path, "char_count": len(text)})
    print(f"Converted {input_path} → {output_path} ({len(text)} chars)", file=sys.stdout)
