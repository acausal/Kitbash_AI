"""Spectrum tool integration for tools.multispectral_analyzer (see SPEC).

LOCKED MVP decision: import the 7 spectrum tools as in-process Python functions
(direct import, no ToolRegistry — registry deferred to post-1.0). When ToolRegistry
exists, refactor run_spectrum() to route through registry.invoke() (mechanical).

Graceful degradation: any spectrum that raises (incl. spaCy missing / model load
failure) is recorded as success=False with the error string; remaining spectra still
run. No TimeoutError enforcement in MVP (Python lacks cross-platform function
timeouts without signal); noted as post-1.0.

NOTE on environment: the 4 spaCy-backed tools (tokenizer/ner/svo/negation_detector)
require `en_core_web_sm` AND a working pydantic. In this venv a leaked Hermes
PYTHONPATH shadows pydantic, so spaCy fails to load. Invoke the Kitbash venv python
with `PYTHONPATH= ` (empty) to drop the leak; e.g.
    PYTHONPATH= .venv/Scripts/python.exe tools/run_TEST.py
Without that prefix those 4 spectra degrade (RuntimeError caught), the other 3 run.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

# --- SPECTRUM -> tool module map (MVP: 7 text spectra) -------------------------
SPECTRUM_TOOL_MAP: Dict[str, str] = {
    "surface": "tokenizer",
    "entities": "ner",
    "semantics": "svo",
    "epistemic": "negation_detector",
    "frequency": "frequency_analysis",
    "semantic_weight": "tfidf_ranker",
    # classification -> naive_bayes_classifier  (deferred: needs trained model)
    # markov         -> markov_chain            (deferred: needs trained model)
    # anomaly        -> anomaly_scorer          (deferred: complex integration)
}

# Default MVP spectrum set (all 7 enabled unless caller overrides).
DEFAULT_SPECTRA: List[str] = list(SPECTRUM_TOOL_MAP.keys())

# Lazy import cache: name -> callable. Avoids importing spaCy at module load.
_IMPL: Dict[str, Callable] = {}


def _get_impl(spectrum_name: str) -> Callable:
    """Return the spectrum's tool callable, importing lazily on first use."""
    if spectrum_name in _IMPL:
        return _IMPL[spectrum_name]
    if spectrum_name == "surface":
        from tools.tokenizer.core import tokenize as f
    elif spectrum_name == "entities":
        from tools.ner.core import extract_entities as f
    elif spectrum_name == "semantics":
        from tools.svo.core import extract_svo as f
    elif spectrum_name == "epistemic":
        from tools.negation_detector.core import detect_negations as f
    elif spectrum_name == "frequency":
        from tools.frequency_analysis.core import analyze_frequencies as f
    elif spectrum_name == "semantic_weight":
        from tools.tfidf_ranker.core import rank_documents as f
    else:
        raise ValueError(f"unknown spectrum '{spectrum_name}'")
    _IMPL[spectrum_name] = f
    return f


def run_spectrum(spectrum_name: str, data: str) -> dict:
    """Invoke one spectrum on `data`; return a standardized result dict.

    Never raises: failures are captured as success=False so other spectra continue.
    """
    tool_id = SPECTRUM_TOOL_MAP.get(spectrum_name, spectrum_name)
    t0 = time.perf_counter()
    try:
        fn = _get_impl(spectrum_name)
        if spectrum_name in ("frequency", "semantic_weight"):
            # These tools take tokens / a query+corpus, not raw data text.
            # For the prism we feed the tokenized form and a single-doc corpus.
            from tools.tokenizer.core import tokenize
            toks = [t.text for t in tokenize(data)]
            if spectrum_name == "frequency":
                raw = fn(toks, {"return_stats": True})
            else:  # semantic_weight (tfidf_ranker)
                raw = fn(data, [{"id": "doc1", "tokens": toks}], {"return_raw": True})
        else:
            raw = fn(data)
        elapsed = int((time.perf_counter() - t0) * 1000)
        return {
            "tool_id": tool_id,
            "success": True,
            "output": _serialize(raw),
            "execution_time_ms": elapsed,
        }
    except Exception as e:  # noqa: BLE001 - intentional broad catch (graceful degradation)
        elapsed = int((time.perf_counter() - t0) * 1000)
        return {
            "tool_id": tool_id,
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "execution_time_ms": elapsed,
        }


def run_all_spectra(data: str, enabled: List[str]) -> Dict[str, dict]:
    """Run all enabled spectra (serial). Returns {spectrum_name: result_dict}."""
    return {name: run_spectrum(name, data) for name in enabled}


def _serialize(obj):
    """Recursively convert tool outputs (dataclasses/lists/dicts) to JSON-safe form.

    spaCy spectra return lists of dataclass instances (Token/SVO/Entity) possibly
    nested; convert every dataclass instance to a dict so the result is JSON-serializable
    even when historical_common.write_output uses a plain json.dumps (no default=).
    """
    import dataclasses

    def conv(o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return {k: conv(v) for k, v in dataclasses.asdict(o).items()}
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [conv(x) for x in o]
        if hasattr(o, "__dict__"):
            return {k: conv(v) for k, v in vars(o).items() if not k.startswith("_")}
        return o

    return conv(obj)
