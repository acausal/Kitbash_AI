"""Token dataclass for tools.tokenizer (see SPEC-tokenizer_v1.md)."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Token:
    text: str        # Original token text
    lemma: str       # Base form (== text unless lemmatize=True)
    pos: str         # Part of speech (NOUN, VERB, ADJ, ...)
    is_stop: bool    # Is this a stop word?
    is_punct: bool   # Is this punctuation?
    is_space: bool   # Is this whitespace?
    idx: int         # Character offset in original text
    doc_idx: int     # Index in the token sequence

    def to_dict(self) -> dict:
        return asdict(self)
