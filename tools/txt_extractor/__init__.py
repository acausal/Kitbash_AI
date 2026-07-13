"""txt_extractor: plain-text -> normalized Markdown-ish text (stdlib only).

Isolation-first tool (see tools/README.md). Allowed imports: stdlib +
optional structured_logger. No orchestrator/sleep_*/redis_*/engine/mtr_*.
"""
from __future__ import annotations
import os, sys

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("txt_extractor")
except Exception:
    _logger = None


def convert_txt_to_markdown(input_path: str, output_path: str) -> None:
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"input file not found: {input_path}")
    if not input_path.lower().endswith(".txt"):
        raise ValueError(f"input is not a .txt file: {input_path}")

    if _logger:
        _logger.log(event_type="extraction_started", data={"source": input_path})

    raw = None
    for enc in ("utf-8", "latin-1"):
        try:
            with open(input_path, "r", encoding=enc) as fh:
                raw = fh.read()
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise RuntimeError(f"Cannot decode file as UTF-8 or Latin-1: {input_path}")

    text = _normalize(raw)
    # empty file is allowed (not an error)
    _write(text, input_path, output_path)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    out = "\n".join(lines)
    while "\n\n\n" in out:  # collapse 3+ blank lines -> 2
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
