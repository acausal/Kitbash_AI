"""negation_detector core: mark tokens within a window of a negation marker.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib, spaCy,
and Kitbash core's structured_logger (read-only helper). No orchestrator/
engine/redis imports.

v1: hardcoded marker list + fixed-distance window. Linguistic scope analysis,
multi-word negations, and double-negative logic are deferred to v2+.
"""
from __future__ import annotations

from typing import List

from .negation_markers import is_negation_marker
from .token_schema import Token

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("negation_detector")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None

_NLP_CACHE: dict = {}


def _load_model(model: str = "en_core_web_sm"):
    if model in _NLP_CACHE:
        return _NLP_CACHE[model]
    try:
        import spacy
    except ImportError as e:
        raise RuntimeError("spaCy not installed. Run: pip install spacy") from e
    try:
        nlp = spacy.load(model)
    except OSError as e:
        raise RuntimeError(
            f"spaCy model '{model}' not installed. "
            f"Run: python -m spacy download {model}"
        ) from e
    _NLP_CACHE[model] = nlp
    return nlp


def detect_negations(text: str, window: int = 5) -> List[Token]:
    """Detect negation in text and mark negated tokens.

    Args:
        text: Raw input text. Empty string is allowed (returns []); None is not.
        window: Token distance (before and after) around each negation marker to
            mark as negated. Must be a positive integer (default: 5).

    Returns:
        List of Token objects with `is_negated` set. Markers themselves are
        included in their own window, so they are marked negated too.

    Raises:
        ValueError: text is None/not a string, or window is not a positive int.
    """
    if text is None or not isinstance(text, str):
        raise ValueError(
            "text must be a string (got "
            f"{'None' if text is None else type(text).__name__})"
        )
    # bool is an int subclass; reject it explicitly so window=True can't slip in.
    if not isinstance(window, int) or isinstance(window, bool) or window < 1:
        raise ValueError(f"window must be a positive integer (got {window!r})")

    nlp = _load_model()
    doc = nlp(text)
    if _logger:
        _logger.log(event_type="negation_detection_started",
                    data={"char_count": len(text), "window": window})

    marker_positions = {
        i for i, tok in enumerate(doc)
        if is_negation_marker(tok.text, tok.lemma_)
    }
    negated = set()
    for pos in marker_positions:
        negated.update(range(max(0, pos - window), min(len(doc), pos + window + 1)))

    tokens = [
        Token(
            text=tok.text,
            lemma=tok.lemma_,
            pos=tok.pos_,
            is_stop=tok.is_stop,
            is_punct=tok.is_punct,
            is_space=tok.is_space,
            idx=tok.idx,
            doc_idx=i,
            is_negated=(i in negated),
        )
        for i, tok in enumerate(doc)
    ]

    if _logger:
        _logger.log(event_type="negation_detection_complete",
                    data={"token_count": len(tokens),
                          "negated_count": sum(1 for t in tokens if t.is_negated),
                          "marker_positions": sorted(marker_positions)})
    return tokens
