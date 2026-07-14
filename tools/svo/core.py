"""svo core: subject-verb-object extraction via spaCy dependency parse.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib, spaCy,
and Kitbash core's structured_logger (read-only helper). No orchestrator/
engine/redis imports.

v1: one SVO per main clause (sent.root as verb), head-word subject/object.
Nested/subordinate clauses, full-span phrases, and SRL are deferred to v2+.
"""
from __future__ import annotations

from typing import List

from .svo_schema import SVO

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("svo")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None

_SUBJ_DEPS = ("nsubj", "nsubjpass")
_OBJ_DEPS = ("dobj", "iobj", "attr")

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


def extract_svo(text: str) -> List[SVO]:
    """Extract subject-verb-object triples from text (main clauses only).

    Args:
        text: Raw input text. Empty string is allowed (returns []); None is not.

    Returns:
        List of SVO objects, one per sentence that has a main verb. Subject and
        object are the head token's text (None when the dependency is absent).
        Sentences without a verb (e.g. "What a day!") are skipped.

    Raises:
        ValueError: text is None or not a string.
        RuntimeError: spaCy or the model is not installed / fails to load.
    """
    if text is None or not isinstance(text, str):
        raise ValueError(
            "text must be a string (got "
            f"{'None' if text is None else type(text).__name__})"
        )

    nlp = _load_model()
    if _logger:
        _logger.log(event_type="svo_extraction_started", data={"char_count": len(text)})

    doc = nlp(text)
    svos: List[SVO] = []
    for sent in doc.sents:
        # Every finite verb in the sentence is a clause to extract. spaCy links
        # coordinated verbs (conj), clausal complements (ccomp), and the root
        # all as VERB tokens, so iterating verbs covers "Alice loves Bob and
        # Charlie hates Eve" (root 'loves' + ccomp 'hates') with no special-casing.
        # A pure auxiliary (dep aux/auxpass) only carries tense/voice for its
        # VERB head (e.g. the "was" in "was announced"); drop it. Copula-only
        # auxiliaries like "is" in "He is a doctor" have dep ROOT and are kept.
        verbs = [t for t in sent
                 if t.pos_ == "VERB"
                 or (t.pos_ == "AUX" and t.dep_ not in ("aux", "auxpass"))]
        if not verbs:
            # No usable main verb (exclamatory fragment, noun-ROOT, etc.).
            continue
        for verb in verbs:
            subject = subject_start = subject_end = None
            obj = obj_start = obj_end = None
            for tok in sent:
                if tok.dep_ in _SUBJ_DEPS and tok.head == verb:
                    subject = tok.text
                    subject_start = tok.idx
                    subject_end = tok.idx + len(tok.text)
                elif tok.dep_ in _OBJ_DEPS and tok.head == verb:
                    obj = tok.text
                    obj_start = tok.idx
                    obj_end = tok.idx + len(tok.text)

            svos.append(SVO(
                subject=subject,
                verb=verb.text,
                obj=obj,
                subject_start=subject_start,
                subject_end=subject_end,
                verb_start=verb.idx,
                verb_end=verb.idx + len(verb.text),
                obj_start=obj_start,
                obj_end=obj_end,
                sentence=sent.text,
                doc_idx=len(svos),
            ))

    if _logger:
        _logger.log(event_type="svo_extraction_complete",
                    data={"svo_count": len(svos),
                          "with_subject": sum(1 for s in svos if s.subject),
                          "with_object": sum(1 for s in svos if s.obj)})
    return svos
