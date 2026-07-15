"""tools.naive_bayes_classifier core (stdlib only).

Train a Naive Bayes text classifier (Bernoulli / Multinomial, Laplace smoothing)
and classify / batch-classify / evaluate. Deterministic. See SPEC.

Outputs follow the SPEC result shapes (tool/version/run_id/timestamp envelope +
classification / model / summary blocks).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from tools.historical_common import normalize_config, now_iso
from .features import bernoulli_features, multinomial_features


def _rid(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _log_likelihood(p: float) -> float:
    return math.log(p) if p > 0 else -1e9


def train_classifier(training_corpus: Sequence[dict], feature_type: str = "bernoulli",
                     smoothing: str = "laplace", config: dict = None) -> dict:
    cfg = normalize_config(config)
    ft = feature_type
    if ft not in ("bernoulli", "multinomial"):
        raise ValueError(f"unknown feature_type {ft}")
    corpus = [{"id": d.get("id", ""), "tokens": d.get("tokens", []), "class": d.get("class")}
              for d in training_corpus]
    classes = sorted({d["class"] for d in corpus})
    class_counts = Counter(d["class"] for d in corpus)
    n_docs = len(corpus)
    # per-class feature stats
    class_token_presence = defaultdict(Counter)   # bernoulli: doc count per token
    class_token_freq = defaultdict(Counter)       # multinomial: total freq per token
    class_doc_count = defaultdict(int)           # docs per class (bernoulli denom)
    class_tok_count = defaultdict(int)           # total tokens per class (multinomial denom)
    vocab = set()
    for d in corpus:
        c = d["class"]
        class_doc_count[c] += 1
        if ft == "bernoulli":
            feats = bernoulli_features(d["tokens"], cfg)
            for t in feats:
                class_token_presence[c][t] += 1
                vocab.add(t)
        else:
            feats = multinomial_features(d["tokens"], cfg)
            for t, f in feats.items():
                class_token_freq[c][t] += f
                class_tok_count[c] += f
                vocab.add(t)
    V = len(vocab)
    likelihoods = {}
    for c in classes:
        lik = {}
        if ft == "bernoulli":
            denom = class_doc_count[c] + 2  # Laplace for binary presence
            for t in vocab:
                cnt = class_token_presence[c].get(t, 0)
                lik[t] = (cnt + 1) / denom
        else:
            denom = class_tok_count[c] + V  # Laplace over vocab
            for t in vocab:
                cnt = class_token_freq[c].get(t, 0)
                lik[t] = (cnt + 1) / denom
        likelihoods[c] = lik
    class_priors = {c: class_counts[c] / n_docs for c in classes}
    # training accuracy
    correct = 0
    for d in corpus:
        pred = _predict(likelihoods, class_priors, d["tokens"], ft, cfg, classes)
        if pred == d["class"]:
            correct += 1
    acc = correct / n_docs if n_docs else 0.0
    # per-class precision/recall on training set
    per_class = {}
    for c in classes:
        tp = sum(1 for d in corpus if d["class"] == c and _predict(likelihoods, class_priors, d["tokens"], ft, cfg, classes) == c)
        fp = sum(1 for d in corpus if d["class"] != c and _predict(likelihoods, class_priors, d["tokens"], ft, cfg, classes) == c)
        fn = sum(1 for d in corpus if d["class"] == c and _predict(likelihoods, class_priors, d["tokens"], ft, cfg, classes) != c)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        per_class[c] = round(prec, 4), round(rec, 4)
    return {
        "tool": "naive_bayes_classifier", "version": "v1",
        "run_id": _rid("nb_train"), "timestamp": now_iso(),
        "input_summary": {"training_documents": n_docs, "classes": classes,
                          "feature_type": ft, "vocabulary_size": V},
        "model": {
            "classes": classes,
            "class_priors": {c: round(p, 4) for c, p in class_priors.items()},
            "class_counts": dict(class_counts),
            "feature_likelihoods": {c: {t: round(v, 4) for t, v in lik.items()}
                                    for c, lik in likelihoods.items()},
            "smoothing": smoothing, "feature_type": ft,
        },
        "training_stats": {
            "accuracy_on_training_set": round(acc, 4),
            "per_class_precision": {c: per_class[c][0] for c in classes},
            "per_class_recall": {c: per_class[c][1] for c in classes},
        },
        "metadata": {"computation_time_ms": 0, "training_documents_used": n_docs},
    }


def _predict(likelihoods, class_priors, tokens, ft, cfg, classes, return_probs=False):
    scores = {}
    for c in classes:
        log_prior = _log_likelihood(class_priors[c])
        if ft == "bernoulli":
            feats = bernoulli_features(tokens, cfg)
            s = log_prior
            for t, lik in likelihoods[c].items():
                s += _log_likelihood(lik) if t in feats else _log_likelihood(1.0 - lik)
        else:
            feats = multinomial_features(tokens, cfg)
            s = log_prior
            for t, f in feats.items():
                lik = likelihoods[c].get(t, 1e-9)
                s += f * _log_likelihood(lik)
        scores[c] = s
    total = 0.0
    exps = {c: math.exp(s - max(scores.values())) for c, s in scores.items()}
    total = sum(exps.values())
    post = {c: e / total for c, e in exps.items()}
    best = max(post, key=post.get)
    if return_probs:
        return best, post
    return best


def classify(model: dict, document: dict, return_probabilities: bool = True) -> dict:
    fm = model["model"]
    classes = fm["classes"]
    class_priors = {c: fm["class_priors"][c] for c in classes}
    likelihoods = {c: fm["feature_likelihoods"][c] for c in classes}
    ft = fm["feature_type"]
    best, post = _predict(likelihoods, class_priors, document.get("tokens", []), ft, {}, classes, return_probs=True)
    contribs = {}
    for c in classes:
        contribs[c] = {t: round(_log_likelihood(likelihoods[c].get(t, 1e-9)), 4)
                       for t in document.get("tokens", [])}
    decision_bits = []
    for c in sorted(classes):
        decision_bits.append(f"{c}: prior={class_priors[c]:.3f}")
    return {
        "tool": "naive_bayes_classifier", "version": "v1",
        "run_id": _rid("nb_classify"), "timestamp": now_iso(),
        "classification": {
            "document_id": document.get("id", ""),
            "predicted_class": best,
            "confidence": round(post[best], 4),
            "posterior_probabilities": {c: round(p, 4) for c, p in post.items()},
            "feature_contributions": contribs,
            "decision_log": "; ".join(decision_bits),
        },
        "metadata": {"computation_time_ms": 0, "model_classes": classes, "feature_type": ft},
    }


def batch_classify(model: dict, documents: Sequence[dict], return_probabilities: bool = True) -> dict:
    classes = model["model"]["classes"]
    preds = [classify(model, d, return_probabilities) for d in documents]
    dist = Counter(p["classification"]["predicted_class"] for p in preds)
    confs = [p["classification"]["confidence"] for p in preds]
    most_conf = max(preds, key=lambda p: p["classification"]["confidence"])["classification"]["predicted_class"]
    return {
        "batch_classification_run_id": _rid("nb_batch"),
        "documents_classified": len(preds),
        "classifications": [p["classification"] for p in preds],
        "summary": {
            "class_distribution": dict(dist),
            "average_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
            "most_confident_class": most_conf,
        },
    }


def evaluate_classifier(model: dict, test_corpus: Sequence[dict]) -> dict:
    classes = model["model"]["classes"]
    tp = Counter(); fp = Counter(); fn = Counter()
    for d in test_corpus:
        true_c = d.get("class")
        pred = classify(model, d, return_probabilities=False)["classification"]["predicted_class"]
        for c in classes:
            if c == true_c and pred == c:
                tp[c] += 1
            elif c != true_c and pred == c:
                fp[c] += 1
            elif c == true_c and pred != c:
                fn[c] += 1
    per_class = {}
    macro_f1 = 0.0
    n = 0
    for c in classes:
        prec = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0.0
        rec = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[c] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1_score": round(f1, 4)}
        macro_f1 += f1
        n += 1
    macro_f1 = round(macro_f1 / n, 4) if n else 0.0
    total = len(test_corpus)
    correct = sum(tp.values())
    return {
        "evaluation_run_id": _rid("nb_eval"),
        "test_documents": total,
        "model_classes": classes,
        "results": {"accuracy": round(correct / total, 4) if total else 0.0,
                    "per_class_metrics": per_class, "macro_f1": macro_f1},
        "metadata": {"computation_time_ms": 0},
    }
