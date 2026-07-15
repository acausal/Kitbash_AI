"""tools.naive_bayes_classifier — train + classify text (see SPEC).

Deterministic Naive Bayes training (Bernoulli / Multinomial) with Laplace
smoothing, plus classify / batch_classify / evaluate. Stateless, stdlib-only.
"""
from .core import train_classifier, classify, batch_classify, evaluate_classifier
from .classifier_schema import Model

__all__ = ["train_classifier", "classify", "batch_classify", "evaluate_classifier", "Model"]
