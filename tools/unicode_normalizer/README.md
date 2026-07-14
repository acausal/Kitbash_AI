# unicode_normalizer

Deterministic one-way Unicode → ASCII transliteration for the text pipeline
(eliminates mojibake before cartridge indexing / tokenizer). Wraps
[`anyascii`](https://pypi.org/project/anyascii/) (Aho-Corasick, zero deps,
pure-Python, deterministic). In the Kitbash `.venv`, `anyascii` is already
present as a transitive dependency of `contractions` — no separate install.

## Library

```python
from tools.unicode_normalizer import normalize_text, normalize_file, detect_mojibake

r = normalize_text("Москва café 😀", preserve_unknown=True)
r["normalized"]          # -> "Moskva cafe :grinning:"
r["changed"]             # True
r["script_types_detected"]  # e.g. ["Cyrillic", "Latin", "Emoji"]
r["mojibake_detected"]   # False

# file in -> out (UTF-8; normalizes line-by-line)
normalize_file("inbox/external/feed.txt", "workspace/feed_clean.txt")

# mojibake probe (heuristic)
detect_mojibake("Ð¼Ð¾Ð¶Ð±Ð°Ðº")["mojibake_detected"]  # True
```

Every function returns a **plain JSON-serializable dict**.

### Behavior notes
- **Transliteration** is whatever `anyascii` produces (defaults only; custom
  mappings are out of scope). Notable library outputs (the SPEC's friendly
  strings differ — see *Spec deviations* below): emoji map to short tokens
  (`:rocket:`, `:grinning:`, `:tada:`), `北京` → `BeiJing` (no space), and
  `Αθήνα` → `Athina`. The tool faithfully honors the library, since the SPEC
  says "use anyascii defaults only."
- **Smart quotes/dashes:** `“ ” ‘ ’` → `"`/`'`; `—`/`–` → `-`.
- **`preserve_unknown=True` (default):** characters with no ASCII mapping (rare
  private-use, U+FFFD) are kept in place; control chars except `\n \t \r` are
  stripped; null bytes always stripped.
- **`preserve_unknown=False` (`--strip`):** after transliteration, unmappable
  and non-ASCII chars are removed.
- **Whitespace:** multiple spaces/tabs collapse to one; leading/trailing
  space/tab trimmed (newlines preserved).
- **Script detection** (`script_types_detected`) is a coarse best-effort
  classifier (Latin, Cyrillic, Greek, CJK, Japanese, Arabic, Hebrew, Emoji,
  Punctuation, Control, …) derived from `unicodedata`.

### Mojibake detection (heuristic — not authoritative)
`detect_mojibake` raises confidence on: presence of U+FFFD replacement char,
UTF-8-misread-as-Latin-1 sequences (`Ð`, `Ñ`, `Ã`, `´`, …), or suspicious
script mixing (Latin + Cyrillic/CJK/Greek). It is a signal, not proof.

### Spec deviations (honor library reality)
| Input | SPEC/TEST says | `anyascii` actually returns |
|-------|----------------|------------------------------|
| `🚀` | `rocket` | `:rocket:` |
| `😀` | `smiley face` | `:grinning:` |
| `🎉` | `party [popper]` | `:tada:` |
| `北京` | `Bei Jing` | `BeiJing` |
| `Αθήνα` | `Athena` | `Athina` |
| em/en dash | `-` (TEST shows `−`, a U+2212 rendering glitch; SPEC+line-30 expect `-`) | `-` |

The TEST doc's em/en dash expected `−` (U+2212 MINUS SIGN) is a display
artifact — `anyascii("—")` and `anyascii("–")` both yield ASCII `-`, which is
what line 30 of the same file expects.

### Error taxonomy (exit codes)
`ValueError` → CLI 1 (non-string input, invalid UTF-8) · `FileNotFoundError` /
`OSError` / `RuntimeError` → CLI 2 (file IO / library failure).

## CLI

```bash
echo "Москва café 😀" | python -m tools.unicode_normalizer normalize
python -m tools.unicode_normalizer normalize "北京 запуск"
python -m tools.unicode_normalizer normalize-file inbox/raw.txt workspace/clean.txt
python -m tools.unicode_normalizer detect-mojibake "Ð¼Ð¾Ð¶Ð±Ð°Ðº"
echo '["café","Москва"]' | python -m tools.unicode_normalizer batch
```

Flags: `--strip` (drop unmappable chars). Exit codes: `0` success · `1`
`ValueError` · `2` `FileNotFoundError`/`OSError`/`RuntimeError`.

## Requirements
- `anyascii` (already in the Kitbash `.venv`; if absent: `pip install anyascii`).
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.unicode_normalizer ...`
