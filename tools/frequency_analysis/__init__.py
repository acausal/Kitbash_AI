"""tools.frequency_analysis — token frequency statistics (see SPEC)."""
from .core import analyze_frequencies, analyze_corpus_frequencies, compute_coverage, frequency_histogram
from .analysis_schema import FrequencyEntry, CorpusFrequencyEntry

__all__ = ["analyze_frequencies", "analyze_corpus_frequencies",
           "compute_coverage", "frequency_histogram",
           "FrequencyEntry", "CorpusFrequencyEntry"]
