# rtf_extractor

RTF (`.rtf`) → clean text. Uses `striprtf` (pure Python). Control words
and embedded objects/images are stripped; text content is extracted
best-effort.

## Non-goals
No structure inference, batch, or bus integration. Malformed RTF is
handled best-effort by striprtf.

## CLI
```
python -m tools.rtf_extractor input.rtf
python -m tools.rtf_extractor input.rtf -o out.md
```
Exit 0 / prints `Converted <in> → <out> (<N> chars)`; exit 1 on failure.

## Library
```python
from tools.rtf_extractor import convert_rtf_to_markdown
convert_rtf_to_markdown("input.rtf", "out.md")
```
Raises: `FileNotFoundError`, `ValueError` (not `.rtf`), `RuntimeError`
(RTF parse failure), `IOError` (write fail). Empty allowed.
