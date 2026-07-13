# html_extractor

HTML (`.html`, `.htm`) → clean text. Stdlib `html.parser.HTMLParser`.
`<script>`/`<style>`/`<meta>`/`<head>` content is skipped; entities are
decoded; whitespace and blank-line runs are normalized.

## Non-goals
No structure inference, batch, or bus integration. Malformed HTML is
parsed best-effort (HTMLParser is forgiving).

## CLI
```
python -m tools.html_extractor input.html
python -m tools.html_extractor input.html -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.html_extractor import convert_html_to_markdown
convert_html_to_markdown("input.html", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.html`/`.htm`),
`RuntimeError` (decode/parse fails), `IOError` (write fail). Empty allowed.
