"""tokenizer core: spaCy-based tokenization (Stage: input sieve / preprocessing).

Isolation-first tool (see tools/README.md). Allowed imports: stdlib, spaCy,
and Kitbash core's structured_logger (read-only helper). No orchestrator/
engine/redis imports.

v1: English only (en_core_web_sm), whitespace + punctuation aware, optional
lemmatization and stop-word removal. Slang/abbrev/multilang deferred to v2+.
"""
from __future__ import annotations

from typing import List

from .token_schema import Token

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("tokenizer")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None

# spaCy models are expensive to load; cache per model name across calls.
_NLP_CACHE: dict = {}


def _load_model(model: str):
    """Load (and cache) a spaCy model. Raise RuntimeError if not installed."""
    if model in _NLP_CACHE:
        return _NLP_CACHE[model]
    try:
        import spacy
    except ImportError as e:
        raise RuntimeError(
            "spaCy not installed. Run: pip install spacy"
        ) from e
    try:
        nlp = spacy.load(model)
    except OSError as e:
        raise RuntimeError(
            f"spaCy model '{model}' not installed. "
            f"Run: python -m spacy download {model}"
        ) from e
    _NLP_CACHE[model] = nlp
    return nlp


def tokenize(
    text: str,
    lemmatize: bool = False,
    remove_stop: bool = False,
    model: str = "en_core_web_sm",
) -> List[Token]:
    """Tokenize text using spaCy.

    Args:
        text: Raw input text. Empty string is allowed (returns []); None is not.
        lemmatize: If True, populate each Token.lemma with the base form.
        remove_stop: If True, exclude stop words from the output.
        model: spaCy model to use (default: en_core_web_sm).

    Returns:
        List of Token objects (empty list if text is empty).

    Raises:
        ValueError: text is None or not a string.
        RuntimeError: spaCy or the model is not installed / fails to load.
    """
    if text is None or not isinstance(text, str):
        raise ValueError(
            "text must be a string (got "
            f"{'None' if text is None else type(text).__name__})"
        )

    nlp = _load_model(model)
    if _logger:
        _logger.log(event_type="tokenization_started",
                    data={"char_count": len(text), "model": model})

    doc = nlp(text)
    tokens: List[Token] = []
    for doc_idx, tok in enumerate(doc):
        if remove_stop and tok.is_stop:
            continue
        tokens.append(Token(
            text=tok.text,
            lemma=tok.lemma_ if lemmatize else tok.text,
            pos=tok.pos_,
            is_stop=tok.is_stop,
            is_punct=tok.is_punct,
            is_space=tok.is_space,
            idx=tok.idx,
            doc_idx=doc_idx,
        ))

    if _logger:
        _logger.log(event_type="tokenization_complete",
                    data={"token_count": len(tokens),
                          "stop_word_count": sum(1 for t in tokens if t.is_stop),
                          "punct_count": sum(1 for t in tokens if t.is_punct)})
    return tokens
