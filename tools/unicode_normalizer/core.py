"""unicode_normalizer core: deterministic Unicode -> ASCII.

Depend: `anyascii` (PyPI, zero-deps). In the Kitbash `.venv` it is already
present as a transitive dependency of `contractions`; no install required.

One-way, deterministic mapping (Unicode -> ASCII). No reversibility.

Error taxonomy (matches the SPEC CLI exit codes):
  ValueError   -> invalid input (non-string), bad UTF-8                 (CLI 1)
  FileNotFoundError -> input file missing                               (CLI 2)
  OSError/RuntimeError -> file IO / library failure                     (CLI 2/3)
"""
from __future__ import annotations

import re
import time
import unicodedata
from typing import Dict, List

import anyascii as _anyascii

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("unicode_normalizer")
except Exception:
    _logger = None


def _log(event: str, **data) -> None:
    if _logger:
        try:
            _logger.log(event_type=event, data=data)
        except Exception:
            pass


# --- script classification -------------------------------------------------- #
_CONTROL_CATS = {"Cc", "Cf", "Cs", "Co", "Cn"}
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _script_of(ch: str) -> str:
    """Best-effort script label for a single character."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        cat = unicodedata.category(ch)
        if ch in ("\n", "\t", "\r"):
            return "Whitespace"
        if cat in _CONTROL_CATS:
            return "Control"
        return "Unknown"
    if name.startswith("CJK") or "IDEOGRAPH" in name or "HANGUL" in name:
        return "CJK"
    if "CYRILLIC" in name:
        return "Cyrillic"
    if "GREEK" in name:
        return "Greek"
    if "HIRAGANA" in name or "KATAKANA" in name:
        return "Japanese"
    if "ARABIC" in name:
        return "Arabic"
    if "HEBREW" in name:
        return "Hebrew"
    if "EMOJI" in name or unicodedata.category(ch) == "So":
        return "Emoji"
    if "LATIN" in name:
        return "Latin"
    if "QUOTATION MARK" in name or "APOSTROPHE" in name:
        return "Punctuation"
    cat = unicodedata.category(ch)
    if cat.startswith("P"):
        return "Punctuation"
    if cat.startswith("L"):
        return "Letter"
    if cat.startswith("N"):
        return "Number"
    if cat.startswith("S"):
        return "Symbol"
    return "Other"


def _detect_scripts(text: str) -> List[str]:
    seen: List[str] = []
    for ch in text:
        if ch.isspace():
            continue
        s = _script_of(ch)
        if s not in seen:
            seen.append(s)
    return seen


# --- core transforms -------------------------------------------------------- #
# Control chars removed (except newline/tab/CR). U+FFFD replacement char
# preserved when preserve_unknown=True (it is a valid character), stripped when
# False. Null byte (\x00) always stripped.
_STRIP_CTRL = dict.fromkeys(
    c for c in range(0x20)  # 0x00-0x1F control bytes (space 0x20 kept)
    if c not in (0x09, 0x0A, 0x0D)  # keep \t \n \r
)


def _normalize_text_impl(text: str, preserve_unknown: bool) -> str:
    if preserve_unknown:
        # anyascii leaves unmappable chars in place; just strip control bytes.
        out = text.translate(_STRIP_CTRL)
        return _anyascii.anyascii(out)
    # strip mode: transliterate then drop anything that is not ASCII.
    out = _anyascii.anyascii(text)
    return "".join(c for c in out if ord(c) < 128 and c != "\ufffd")


# --- mojibake heuristics ---------------------------------------------------- #
# UTF-8 bytes misread as Latin-1 produce telltale ASCII garbage sequences.
_MOJIBAKE_SEQUENCES = ["Ð", "Ñ", "Ò", "Ó", "Ô", "Õ", "Ö", "Ø", "ð", "ñ", "´", "Ã"]
_REPLACEMENT = "\ufffd"


def _detect_mojibake_impl(text: str) -> Dict:
    analysis: Dict[str, bool] = {
        "high_ratio_of_unusual_control_sequences": False,
        "unreasonable_byte_patterns": False,
        "script_mixing_suspicious": False,
    }
    signals = 0.0

    if _REPLACEMENT in text:
        analysis["high_ratio_of_unusual_control_sequences"] = True
        signals += 0.6

    seq_hits = sum(text.count(s) for s in _MOJIBAKE_SEQUENCES)
    if seq_hits > 0:
        analysis["unreasonable_byte_patterns"] = True
        signals += min(0.5, 0.1 * seq_hits)

    scripts = _detect_scripts(text)
    # Latin + Cyrillic/Greek/CJK co-occurring is a classic mis-decoded mix.
    if "Latin" in scripts and any(s in scripts for s in ("Cyrillic", "CJK", "Greek")):
        analysis["script_mixing_suspicious"] = True
        signals += 0.1

    detected = signals > 0.0
    confidence = round(min(1.0, signals), 2)
    likely = "UTF-8 decoded as Latin-1" if detected else None
    return {
        "mojibake_detected": detected,
        "confidence": confidence,
        "likely_source_encoding": likely,
        "analysis": analysis,
    }


# --- public API ------------------------------------------------------------- #
def normalize_text(text: str, preserve_unknown: bool = True) -> dict:
    if not isinstance(text, str):
        raise ValueError(f"normalize_text expects str, got {type(text).__name__}")
    _log("normalize_started", preserve_unknown=preserve_unknown, length=len(text))
    start = time.perf_counter()

    normalized = _normalize_text_impl(text, preserve_unknown)
    # collapse runs of spaces (but keep newlines/tabs) for clean output
    normalized = re.sub(r"[ \t]+", " ", normalized).strip(" \t")

    mojibake = _detect_mojibake_impl(text)["mojibake_detected"]
    scripts = _detect_scripts(text)

    result = {
        "operation": "normalize_text",
        "original": text,
        "normalized": normalized,
        "changed": normalized != text,
        "char_count": {"original": len(text), "normalized": len(normalized)},
        "mojibake_detected": mojibake,
        "script_types_detected": scripts,
        "preserve_unknown_mode": preserve_unknown,
    }
    _log("normalize_complete", changed=result["changed"],
         elapsed_ms=round((time.perf_counter() - start) * 1000, 2))
    return result


def normalize_file(input_path: str, output_path: str,
                   preserve_unknown: bool = True) -> dict:
    if not isinstance(input_path, str) or not isinstance(output_path, str):
        raise ValueError("input_path and output_path must be str")
    _log("normalize_file_started", input_path=input_path, output_path=output_path)
    start = time.perf_counter()
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        raise
    except UnicodeDecodeError as e:
        raise ValueError(f"input file is not valid UTF-8: {e}")
    except OSError as e:
        raise OSError(f"failed to read {input_path!r}: {e}")

    lines = content.split("\n")
    out_lines = [normalize_text(ln, preserve_unknown)["normalized"] for ln in lines]
    normalized_text = "\n".join(out_lines)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(normalized_text)
    except OSError as e:
        raise OSError(f"failed to write {output_path!r}: {e}")

    scripts = _detect_scripts(content)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    result = {
        "operation": "normalize_file",
        "input_path": input_path,
        "output_path": output_path,
        "bytes_read": len(content.encode("utf-8")),
        "bytes_written": len(normalized_text.encode("utf-8")),
        "lines_processed": len(out_lines),
        "normalized": True,
        "mojibake_detected": _detect_mojibake_impl(content)["mojibake_detected"],
        "script_types_detected": scripts,
        "processing_time_ms": elapsed,
    }
    _log("normalize_file_complete", bytes_read=result["bytes_read"],
         bytes_written=result["bytes_written"], elapsed_ms=elapsed)
    return result


def detect_mojibake(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError(f"detect_mojibake expects str, got {type(text).__name__}")
    det = _detect_mojibake_impl(text)
    result = {
        "operation": "detect_mojibake",
        "original": text,
        **det,
        "suggested_fix": "normalize_text(text)" if det["mojibake_detected"] else "",
    }
    _log("mojibake_detected" if det["mojibake_detected"] else "mojibake_clean",
         confidence=det["confidence"])
    return result
