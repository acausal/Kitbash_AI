"""Dataclasses for tools.naive_bayes_classifier (see SPEC)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Model:
    classes: List[str]
    class_priors: Dict[str, float]
    class_counts: Dict[str, int]
    feature_likelihoods: Dict[str, Dict[str, float]]
    smoothing: str = "laplace"
    feature_type: str = "bernoulli"
