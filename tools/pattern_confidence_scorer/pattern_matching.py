"""Pattern matching + confusion-matrix construction for pattern_confidence_scorer.

Pure stdlib. Classifies each observation (trace or dream-bucket) for a given
pattern into TP/FP/TN/FN per the SPEC's confusion-matrix definition:

  TP = pattern fired AND outcome correct
  FP = pattern fired AND outcome incorrect
  TN = pattern did NOT fire AND outcome correct
  FN = pattern did NOT fire AND outcome incorrect
"""
from __future__ import annotations

from typing import Dict, List

from .metrics import ConfusionMatrix

# Outcome strings considered "correct" (positive class).
_POSITIVE_OUTCOMES = {"success", "correct"}
# Outcome strings considered "incorrect" (negative class).
_NEGATIVE_OUTCOMES = {"failure", "false_positive", "incorrect", "collision",
                      "violation", "consistency_violation"}


def _is_correct(outcome: str) -> bool:
    if outcome in _POSITIVE_OUTCOMES:
        return True
    if outcome in _NEGATIVE_OUTCOMES:
        return False
    # Unknown outcome token: treat as correct (success-like) to avoid skew.
    return True


def sequence_fires(pattern_seq: List[str], trace_seq: List[str]) -> bool:
    """Contiguous-subsequence match (pattern is a substring window of trace)."""
    if not pattern_seq:
        return False
    n, m = len(trace_seq), len(pattern_seq)
    if m > n:
        return False
    for i in range(n - m + 1):
        if trace_seq[i:i + m] == pattern_seq:
            return True
    return False


def collision_fires(pattern_pair: List, obs: Dict) -> bool:
    """Does this collision observation trigger the pair pattern?

    A `false_positive` observation mentioning EITHER id of the pair fires the
    pattern (the retriever returned a wrong id on a collision involving one of
    the pair's ids). Exact-pair `false_positive` = TRUE POSITIVE; other-pair
    `false_positive` = FALSE POSITIVE. Non-`false_positive` observations
    (collision_cluster, success, …) do NOT fire → treated as true negatives.
    """
    if not pattern_pair or len(pattern_pair) < 2:
        return False
    if obs.get("type") != "false_positive":
        return False
    a, b = pattern_pair[0], pattern_pair[1]
    ret, cor = obs.get("returned_id"), obs.get("correct_id")
    return ret == a or ret == b or cor == a or cor == b


def grain_chain_fires(pattern_grains: List[str], trace_grains: List[str]) -> bool:
    """All pattern grains present in trace, order preserved (subsequence)."""
    return sequence_fires(pattern_grains, trace_grains)


def pattern_elements(pattern: Dict, pattern_type: str):
    """Return (elements, fires_fn, is_correct_outcome_fn)."""
    if pattern_type == "collision":
        pair = pattern.get("collision_pair", [])
        return pair, None, None
    if pattern_type == "grain_chain":
        grains = pattern.get("sequence", pattern.get("grains", []))
        return grains, None, None
    # default: sequence
    return pattern.get("sequence", []), None, None


def build_confusion(pattern: Dict, observations: List[Dict],
                    pattern_type: str = "sequence") -> ConfusionMatrix:
    """Classify every observation of `pattern` into a ConfusionMatrix."""
    tp = fp = tn = fn = 0
    if pattern_type == "collision":
        # For collision patterns, a `false_positive` observation is the positive
        # class (it records a real collision). Mentioning either pair id fires
        # the pattern; exact-pair = TP, other-pair = FP; non-`false_positive`
        # observations = TN (pattern correctly did not fire).
        pair = pattern.get("collision_pair", [])
        for obs in observations:
            fires = collision_fires(pair, obs)
            exact = (obs.get("returned_id") == pair[0] and obs.get("correct_id") == pair[1]) if len(pair) >= 2 else False
            correct = fires and exact
            if fires and correct:
                tp += 1
            elif fires and not correct:
                fp += 1
            elif (not fires) and (obs.get("type") == "false_positive"):
                # mention-related false_positive that didn't fire (shouldn't happen)
                tn += 1
            elif not fires:
                tn += 1
            else:
                fn += 1
        return ConfusionMatrix(tp, fp, tn, fn, tp + fp + tn + fn)

    # sequence / grain_chain: match order semantics
    if pattern_type == "grain_chain":
        pat_seq = pattern.get("sequence", pattern.get("grains", []))
    else:
        pat_seq = pattern.get("sequence", [])
    for obs in observations:
        seq = obs.get("sequence", obs.get("grain_sequence", []))
        fires = sequence_fires(pat_seq, seq)
        correct = _is_correct(obs.get("outcome", "success"))
        if fires and correct:
            tp += 1
        elif fires and not correct:
            fp += 1
        elif (not fires) and correct:
            tn += 1
        else:
            fn += 1
    return ConfusionMatrix(tp, fp, tn, fn, tp + fp + tn + fn)
