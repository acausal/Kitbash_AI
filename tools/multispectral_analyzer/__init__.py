"""tools.multispectral_analyzer — prism tool: fingerprint data through parallel spectra.

Public API: analyze_multispectral. MVP = 7 text spectra (classification/markov/
anomaly deferred). Direct in-process import of spectrum tools (no ToolRegistry;
registry deferred to post-1.0). See README + SPEC-multispectral_analyzer_v1.md.
"""
from .core import analyze_multispectral, detect_divergences
from .spectrum_tools import SPECTRUM_TOOL_MAP, DEFAULT_SPECTRA

__all__ = [
    "analyze_multispectral",
    "detect_divergences",
    "SPECTRUM_TOOL_MAP",
    "DEFAULT_SPECTRA",
]
