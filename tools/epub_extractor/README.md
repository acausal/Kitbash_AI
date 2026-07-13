# epub_extractor

EPUB (`.epub`) → clean text. Uses `ebooklib` (pure Python). Each document
item (chapter) is parsed with stdlib `HTMLParser` (same as `html_extractor`,
skipping `script`/`style`/`meta`/`head`); chapters are concatenated and
separated by `\n--- CHAPTER ---\n`. EPUB2 and EPUB3 are both supported.

## Non-goals
No structure inference, TOC navigation, OCR, batch, or bus integration.
Embedded images are skipped.

## CLI
```
python -m tools.epub_extractor input.epub
python -m tools.epub_extractor input.epub -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.epub_extractor import convert_epub_to_markdown
convert_epub_to_markdown("input.epub", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.epub`), `RuntimeError`
(EPUB parse failure, e.g. corrupted ZIP), `IOError` (write fail).
Empty allowed.
