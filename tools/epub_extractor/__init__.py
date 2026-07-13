"""epub_extractor: EPUB -> clean text (ebooklib + stdlib HTMLParser).

Isolation-first tool (see tools/README.md). Allowed: ebooklib + stdlib
+ optional structured_logger. No orchestrator/sleep_*/redis_*/engine/mtr_*.
"""
from __future__ import annotations
import os, sys
from html.parser import HTMLParser

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("epub_extractor")
except Exception:
    _logger = None

_EXTS = (".epub",)
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


def _html_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    lines = [ln.strip() for ln in "".join(p._buf).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln]
    out = "\n".join(lines)
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip()


def convert_epub_to_markdown(input_path: str, output_path: str) -> None:
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"input file not found: {input_path}")
    if not input_path.lower().endswith(_EXTS):
        raise ValueError(f"input is not a .epub file: {input_path}")

    if _logger:
        _logger.log(event_type="extraction_started", data={"source": input_path})

    try:
        from ebooklib import epub
        import ebooklib
        book = epub.read_epub(input_path)
        chapters = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            raw = item.get_content().decode("utf-8", errors="replace")
            t = _html_text(raw)
            if t.strip():
                chapters.append(t)
    except Exception as e:
        raise RuntimeError(f"EPUB parse failed: {e}") from e

    text = "\n--- CHAPTER ---\n".join(chapters)  # empty epub allowed
    text = text + "\n" if text.strip() else ""
    _write(text, input_path, output_path)


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
