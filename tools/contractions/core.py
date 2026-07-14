"""contractions core: deterministic English contraction expansion.

Wraps the `contractions` PyPI library (v0.1.73). `fix()` performs the actual
substitution and preserves case per the library. This module adds:
  - position tracking (1-based word index of each contraction)
  - single-word expansion + membership test
  - a full contraction dictionary for reference

NOTE on the SPEC: the SPEC references `contractions.CONTRACTION_MAP`, which does
not exist in installed v0.1.73. We instead merge the library's real dicts
(contractions_dict + leftovers_dict + slang_dict). The library does NOT expand
possessives (e.g. "John's" stays "John's"); we honor the library's actual
behavior rather than the SPEC's stale example for case 5.

Exit taxonomy: ValueError -> invalid input (CLI 1); RuntimeError -> library
failure (CLI 2).
"""
from __future__ import annotations

import re
import traceback
from typing import Any, Dict, List, Optional

import contractions as _C

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("contractions")
except Exception:
    _logger = None

_TOKEN_RE = re.compile(r"\S+")
# Split a token into (leading_punct, core, trailing_punct). Core keeps
# apostrophes (contractions); leading/trailing captures surrounding
# punctuation so it is preserved around the expansion.
_PUNCT_RE = re.compile(r"^([^\w']*)(.*?)([^\w']*)$", re.UNICODE)


def _split_punct(token: str):
    m = _PUNCT_RE.match(token)
    if not m:
        return "", token, ""
    return m.group(1), m.group(2), m.group(3)

# Build the merged contraction map from the real library dicts. The library's
# keys are mixed-case ("I'll", "don't", ...), so we also keep a lowercased-key
# index for case-insensitive lookup (values keep their library casing, e.g.
# "I will"; case is re-applied to the input token by _apply_case).
_MERGED: Dict[str, str] = {}
for _name in ("slang_dict", "leftovers_dict", "contractions_dict"):
    _d = getattr(_C, _name, None)
    if isinstance(_d, dict):
        _MERGED.update(_d)
_MERGED_LOWER: Dict[str, str] = {k.lower(): v for k, v in _MERGED.items()}


def _log(event: str, **data) -> None:
    if _logger:
        try:
            _logger.log(event_type=event, data=data)
        except Exception:
            pass


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text)


def _expand_word_raw(word: str) -> Optional[str]:
    """Return the canonical expansion (library casing) if `word` is a known
    contraction, else None. Lookup is case-insensitive via `_MERGED_LOWER`."""
    if word in _MERGED:
        return _MERGED[word]
    low = word.lower()
    if low in _MERGED_LOWER:
        return _MERGED_LOWER[low]
    return None


def expand_word(word: str, preserve_case: bool = True) -> Dict[str, Any]:
    """Expand a single word if it is a contraction.

    `word` is treated as a single lexical item: we test it directly (and its
    lowercased form) against the dictionary. Adjacent punctuation in a multi-
    token phrase is stripped for the lookup, then re-attached, so
    "don't," matches "don't".
    """
    if word is None:
        raise ValueError("word must be a string, got None")
    if not isinstance(word, str):
        raise ValueError(f"word must be a string, got {type(word).__name__}")
    if word == "":
        return {"operation": "expand_word", "word": word,
                "is_contraction": False, "expanded": word, "case_preserved": True}

    lead, core_tok, trail = _split_punct(word)
    core = _expand_word_raw(core_tok)
    if core is None:
        return {"operation": "expand_word", "word": word,
                "is_contraction": False, "expanded": word, "case_preserved": True}

    if preserve_case:
        expanded = _apply_case(core, core_tok, word)
    else:
        # non-preserve: normalize to canonical lowercase form
        expanded = core.lower()
    return {"operation": "expand_word", "word": word,
            "is_contraction": True, "expanded": lead + expanded + trail,
            "case_preserved": preserve_case}


def _apply_case(expansion: str, stripped: str, original: str) -> str:
    """Mirror contractions.fix case behavior for a single token."""
    if stripped.isupper() and stripped:
        return expansion.upper()
    if stripped[:1].isupper():
        return expansion[:1].upper() + expansion[1:]
    return expansion


def expand_contractions(text: str, preserve_case: bool = True) -> Dict[str, Any]:
    """Expand all contractions in `text`, tracking word-level positions."""
    if text is None:
        raise ValueError("text must be a string, got None")
    if text == "":
        raise ValueError("text must be a non-empty string")

    _log("expansion_started", text_length=len(text),
         preserve_case=preserve_case, case_preserved=preserve_case)
    try:
        tokens = _tokenize(text)
        expanded_tokens: List[str] = []
        instances: List[Dict[str, Any]] = []
        for idx, tok in enumerate(tokens, start=1):
            lead, core_tok, trail = _split_punct(tok)
            core = _expand_word_raw(core_tok)
            if core is not None:
                if preserve_case:
                    repl = _apply_case(core, core_tok, tok)
                else:
                    repl = core.lower()
                repl = lead + repl + trail
                expanded_tokens.append(repl)
                instances.append({
                    "contraction": tok,
                    "expansion": repl,
                    "position": idx,
                })
            else:
                expanded_tokens.append(tok)
        expanded_text = " ".join(expanded_tokens)
        result: Dict[str, Any] = {
            "operation": "expand_contractions",
            "preserve_case": preserve_case,
            "original_text": text,
            "expanded_text": expanded_text,
            "contractions_found": len(instances),
            "contractions_list": instances,
        }
        _log("expansion_complete", contractions_found=len(instances))
        return result
    except Exception as e:  # pragma: no cover - library failure path
        _log("expansion_failed", error=traceback.format_exc(limit=2))
        raise RuntimeError(f"contraction expansion failed: {e}")


def list_contractions() -> Dict[str, Any]:
    """Return the full merged contraction dictionary (791 entries in v0.1.73)."""
    return {
        "operation": "list_contractions",
        "total_contractions": len(_MERGED),
        "contractions": dict(_MERGED),
    }
