"""Token dataclass for tools.negation_detector.

Mirrors tools.tokenizer.Token with one added field, `is_negated`. Kept as a
separate schema so the tokenizer's Token (which has no is_negated) is untouched.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Token:
    text: str        # Original token text
    lemma: str       # Base form
    pos: str         # Part of speech
    is_stop: bool    # Is this a stop word?
    is_punct: bool   # Is this punctuation?
    is_space: bool   # Is this whitespace?
    idx: int         # Character offset in original text
    doc_idx: int     # Index in the token sequence
    is_negated: bool  # Is this token within a negation window?

    def to_dict(self) -> dict:
        return asdict(self)
