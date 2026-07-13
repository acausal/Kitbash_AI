"""html_extractor: HTML -> clean text (stdlib HTMLParser).

Isolation-first tool (see tools/README.md). Allowed: stdlib + optional
structured_logger. No orchestrator/sleep_*/redis_*/engine/mtr_*.
"""
from __future__ import annotations
import os, sys
from html.parser import HTMLParser

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("html_extractor")
except Exception:
    _logger = None

_SKIP = {"script", "style", "meta", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._buf = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            self._buf.append(data)


def convert_html_to_markdown(input_path: str, output_path: str) -> None:
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"input file not found: {input_path}")
    low = input_path.lower()
    if not (low.endswith(".html") or low.endswith(".htm")):
        raise ValueError(f"input is not a .html/.htm file: {input_path}")

    if _logger:
        _logger.log(event_type="extraction_started", data={"source": input_path})

    try:
        with open(input_path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except UnicodeDecodeError:
        try:
            with open(input_path, "r", encoding="latin-1") as fh:
                raw = fh.read()
        except Exception as e:
            raise RuntimeError(f"Cannot decode HTML as UTF-8 or Latin-1: {e}") from e
    except OSError as e:
        raise IOError(f"cannot read input {input_path}: {e}") from e

    try:
        parser = _TextExtractor()
        parser.feed(raw)
        raw_text = "".join(parser._buf)
    except Exception as e:
        raise RuntimeError(f"HTML parse failed: {e}") from e

    text = _normalize(raw_text)  # empty HTML allowed
    _write(text, input_path, output_path)


def _normalize(text: str) -> str:
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln != ""]
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
