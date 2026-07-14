"""Metric computation for tools.pattern_confidence_scorer.

Standard, deterministic, textbook confusion-matrix metrics. (See SPEC note in
README: the TEST-pattern_confidence_scorer_examples.json's FPR/specificity
values use a non-standard definition and are known-bad references; this module
implements the correct textbook forms.)

Confusion matrix layout (per pattern vs. observations):
  TP = pattern fired AND outcome correct (success / correct / not false_positive)
  FP = pattern fired AND outcome incorrect (failure / false_positive)
  TN = pattern did NOT fire AND outcome correct
  FN = pattern did NOT fire AND outcome incorrect

Metrics:
  precision = TP / (TP + FP)                 (0.0 if no fires)
  recall    = TP / (TP + FN)                 (= TPR; 0.0 if no correct outcomes)
  f1        = 2*P*R / (P + R)               (0.0 if P+R==0)
  tpr       = recall
  fpr       = FP / (FP + TN)                (0.0 if no incorrect outcomes)
  specificity = TN / (FP + TN) = 1 - fpr
  support   = TP + FP                        (observations where pattern fired)
"""
from __future__ import annotations

from typing import NamedTuple


class ConfusionMatrix(NamedTuple):
    tp: int
    fp: int
    tn: int
    fn: int
    total: int


def _safe_div(num: int, den: int) -> float:
    return (num / den) if den else 0.0


def compute_metrics(cm: ConfusionMatrix) -> dict:
    tp, fp, tn, fn, total = cm
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    fpr = _safe_div(fp, fp + tn)
    specificity = _safe_div(tn, tn + fp)  # == 1 - fpr
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "true_positive_rate": round(recall, 4),
        "false_positive_rate": round(fpr, 4),
        "specificity": round(specificity, 4),
        "f1_score": round(f1, 4),
        "support": tp + fp,
    }


def reliability_level(f1: float) -> str:
    if f1 >= 0.75:
        return "high"
    if f1 >= 0.5:
        return "medium"
    return "low"


# Flag thresholds (from SPEC confidence-flag table).
LOW_SAMPLE_SUPPORT = 20
HIGH_FPR = 0.3
HIGH_FNR = 0.4
LOW_F1 = 0.5


def confidence_flag(metrics: dict, support: int) -> str:
    """Return the single most severe flag, or 'none'.

    Priority: low_sample_size (small-n can't support any rate claim) >
    high_false_positive_rate (FPR>HIGH_FPR) > low_f1_score (f1<LOW_F1) >
    low_recall (recall<0.5). Small samples are flagged as low_sample_size
    rather than over-interpreting FPR/recall.
    """
    if support < LOW_SAMPLE_SUPPORT:
        return "low_sample_size"
    if metrics["false_positive_rate"] > HIGH_FPR:
        return "high_false_positive_rate"
    if metrics["f1_score"] < LOW_F1:
        return "low_f1_score"
    if metrics["recall"] < 0.5:
        return "low_recall"
    return "none"


def sample_size_note(support: int) -> str:
    if support < LOW_SAMPLE_SUPPORT:
        return f"n={support} (recommend n>={LOW_SAMPLE_SUPPORT} for reliable scoring)"
    return f"n={support} (sufficient)"
