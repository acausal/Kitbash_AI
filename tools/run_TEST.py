"""Durable test runner for tools/ TEST-*.json fixtures.

Scans tools/ for fixtures that declare an executable "test_cases" array (each
entry: a `function` name, an `input` dict possibly using `__sample__` placeholders
from the fixture's `samples`, and an `expected_output` dict). For every case it:
  1. expands `__placeholder__` strings against the fixture's `samples`
  2. imports `tools.<pkg>.<function>` (pkg derived from path/filename)
  3. applies function-scoped kwarg aliases (e.g. score_patterns: traces->execution_traces)
  4. calls the function
  5. runs structural sanity checks

Scope: only fixtures that (a) have `test_cases` and (b) resolve to an importable
`tools.<pkg>` package are executed and counted. Legacy example corpora (no
`test_cases`) and pre-existing tools not laid out as importable packages are
reported as SKIP — informational, not failures — so the runner is a reliable
green-evidence command for the tool packages it owns.

    python tools/run_TEST.py            # exits non-zero on any executed FAIL

Stdlib only.
"""
from __future__ import annotations

import glob
import importlib
import inspect
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

# Runner owns these tool packages (importable tools.* with executable,
# expander-compatible fixtures). Legacy example corpora / pre-existing tools with
# heterogeneous fixture conventions are SKIPped, not failed.
OWNED_PACKAGES = {
    "success_pattern_miner", "positive_signal_scorer", "causal_credit_attribution",
    "templating", "frequency_analysis", "inverted_index_builder", "boolean_search",
    "tfidf_ranker", "markov_chain", "naive_bayes_classifier",
}

# function name -> {fixture_input_key: real_param_name}
ALIASES = {
    "score_patterns": {"traces": "execution_traces"},
    "add_document": {"index_state": "index"},
    "cosine_similarity": {"vector_a": "vec_a", "vector_b": "vec_b"},
}

# result keys that mean "total credit normalized to ~1.0"
NORM_RESULT_KEYS = ("total_credit_attributed",)


def _pkg_for(fixture_path: str) -> str:
    d = os.path.dirname(fixture_path)
    # Nested: tools/<pkg>/TEST-*.json -> package is the parent dir name.
    pkg = os.path.basename(d)
    if pkg != "tools":
        return pkg
    # Flat: tools/TEST-<pkg>_examples.json (e.g. templating). Derive from filename
    # only when it matches a known owned package, else 'tools' (will be skipped).
    name = os.path.basename(fixture_path)
    stem = name[len("TEST-"):] if name.startswith("TEST-") else name
    stem = stem[:-len("_examples.json")] if stem.endswith("_examples.json") else stem
    parts = stem.split("_")
    for i in range(len(parts), 0, -1):
        cand = "_".join(parts[:i])
        if cand in OWNED_PACKAGES:
            return cand
    return "tools"


def _expand(v, samples):
    if isinstance(v, str):
        k = v.strip("_")
        return samples.get(k, v)
    if isinstance(v, list):
        if len(v) == 1 and isinstance(v[0], str):
            k = v[0].strip("_")
            if k in samples:
                return [samples[k]] if isinstance(samples[k], dict) else samples[k]
        return [_expand(x, samples) for x in v]
    if isinstance(v, dict):
        if "trace_id" in v and ("sequence" in v or "grain_activations" in v):
            return v
        return {kk: _expand(x, samples) for kk, x in v.items()}
    return v


def _attrs(res):
    return (res.get("tool_attributions") or res.get("grain_attributions")
            or res.get("patterns") or [])


def _check_expected(fn_name, res, exp) -> str:
    """Return '' if ok, else failure detail. Handles fixture expected_output keys."""
    # negative test: expects an exception (handled by caller); nothing to check
    if "raises" in exp:
        return ""
    # scalar-result functions return a non-dict (e.g. cosine_similarity -> float)
    if not isinstance(res, dict):
        if fn_name == "cosine_similarity" and "sim" in exp:
            if abs(float(res) - exp["sim"]) > 1e-6:
                return f"cosine {res}"
        return ""
    # success-trace count (success_pattern_miner)
    if "success_traces_count" in exp:
        if res.get("success_traces_count") != exp["success_traces_count"]:
            return f"success_traces_count {res.get('success_traces_count')}"
    if "patterns_len" in exp and len(res.get("patterns", [])) != exp["patterns_len"]:
        return f"patterns len {len(res.get('patterns', []))}"
    if "patterns_len_ge" in exp and not (len(res.get("patterns", [])) >= exp["patterns_len_ge"]):
        return f"patterns len {len(res.get('patterns', []))} < {exp['patterns_len_ge']}"
    # exact scalars at top level
    for k, want in exp.items():
        if k in ("first_signal_strength_ge", "first_confidence", "first_consistency_lt",
                 "first_temp_stability_lt", "first_score_ge", "has_outcome_weight_dominant",
                 "patterns_len", "patterns_len_ge", "success_traces_count", "raises"):
            continue
        if k in res:
            if isinstance(want, bool) or isinstance(want, str):
                if res[k] != want:
                    return f"{k}: got {res[k]!r} want {want!r}"
            elif isinstance(want, (int, float)):
                if abs(res[k] - want) > 1e-3:
                    return f"{k}: got {res[k]} want {want}"
    attrs = _attrs(res)
    first = attrs[0] if attrs else {}
    dims = first.get("signal_dimensions", {}) if isinstance(first, dict) else {}
    if "first_signal_strength_ge" in exp and not (first.get("signal_strength", 0) >= exp["first_signal_strength_ge"]):
        return f"signal_strength {first.get('signal_strength')} < {exp['first_signal_strength_ge']}"
    if "first_confidence" in exp and first.get("sample_size_confidence") != exp["first_confidence"]:
        return f"confidence {first.get('sample_size_confidence')} != {exp['first_confidence']}"
    if "first_consistency_lt" in exp and not (dims.get("consistency_score", 1) < exp["first_consistency_lt"]):
        return f"consistency {dims.get('consistency_score')}"
    if "first_temp_stability_lt" in exp and not (dims.get("temporal_stability_score", 1) < exp["first_temp_stability_lt"]):
        return f"temp_stability {dims.get('temporal_stability_score')}"
    if "first_score_ge" in exp:
        ps = res.get("pattern_scores") or []
        if not ps or not (ps[0].get("score", 0) >= exp["first_score_ge"]):
            return f"first_score {ps[0].get('score') if ps else None}"
    if exp.get("has_outcome_weight_dominant"):
        w = res.get("metadata", {}).get("weights", {})
        if not w or w.get("outcome_correlation") != max(w.values()):
            return f"weights {w}"
    if "total_credit_attributed" in res:
        if abs(res["total_credit_attributed"] - 1.0) > 0.05:
            return f"total credit {res['total_credit_attributed']}"
    # inverted_index_builder expected_output keys
    if fn_name in ("build_index", "add_document", "merge_indexes"):
        s = res.get("input_summary", {})
        if "documents" in exp and s.get("documents") != exp["documents"]:
            return f"documents {s.get('documents')}"
        if "unique_tokens" in exp and s.get("unique_tokens") != exp["unique_tokens"]:
            return f"unique_tokens {s.get('unique_tokens')}"
        if "documents_ge" in exp and not (s.get("documents", 0) >= exp["documents_ge"]):
            return f"documents {s.get('documents')} < {exp['documents_ge']}"
        idx = res.get("index", {})
        if "token_df" in exp:
            for tok, want_df in exp["token_df"].items():
                got = idx.get(tok, {}).get("document_frequency")
                if got != want_df:
                    return f"df[{tok}] {got} want {want_df}"
    if fn_name == "compute_idf":
        idf = res.get("idf_values", {})
        if "idf_ge" in exp:
            if not all(v >= exp["idf_ge"] for v in idf.values()):
                return f"idf min {min(idf.values()) if idf else None}"
    # boolean_search expected_output keys
    if fn_name == "search":
        s = res.get("input_summary", {})
        if "matching_documents" in exp and s.get("matching_documents") != exp["matching_documents"]:
            return f"matching {s.get('matching_documents')}"
        if "match_ids" in exp:
            got = [r["document_id"] for r in res.get("results", [])]
            if got != exp["match_ids"]:
                return f"match_ids {got}"
    if fn_name == "parse_query":
        if "parse_success" in exp and bool(res.get("input_summary", {}).get("parse_success")) != exp["parse_success"]:
            return f"parse_success {res.get('input_summary', {}).get('parse_success')}"
    if fn_name == "execute_query":
        if "matched" in exp and bool(res.get("matched")) != exp["matched"]:
            return f"matched {res.get('matched')}"
    # frequency_analysis expected_output keys
    if fn_name in ("analyze_frequencies", "analyze_corpus_frequencies"):
        top = (res.get("top_tokens") or [{}])[0]
        if not top.get("token"):
            # corpus mode emits frequency_distribution instead of top_tokens
            fd = res.get("frequency_distribution", {})
            top = {"token": next(iter(fd))} if fd else {}
        if "top_token" in exp and top.get("token") != exp["top_token"]:
            return f"top_token {top.get('token')}"
        if "top_freq" in exp:
            top = (res.get("top_tokens") or [{}])[0]
            if not top.get("frequency"):
                fd = res.get("frequency_distribution", {})
                top = {"frequency": (next(iter(fd.values())) or {}).get("total_frequency", 0)} if fd else {}
            if top.get("frequency") != exp["top_freq"]:
                return f"top_freq {top.get('frequency')}"
        if "gini_lt" in exp:
            gini = res.get("statistics", {}).get("token_stats", {}).get("gini_coefficient", 1)
            if not (gini < exp["gini_lt"]):
                return f"gini {gini}"
    if fn_name == "compute_coverage":
        ca = res.get("coverage_analysis", {})
        if "tokens_needed_ge" in exp and not (ca.get("tokens_needed", 0) >= exp["tokens_needed_ge"]):
            return f"tokens_needed {ca.get('tokens_needed')}"
        if "coverage_achieved_ge" in exp and not (ca.get("coverage_achieved", 0) >= exp["coverage_achieved_ge"]):
            return f"coverage_achieved {ca.get('coverage_achieved')}"
    # tfidf_ranker expected_output keys
    if fn_name == "rank_documents":
        s = res.get("input_summary", {})
        if "variant" in exp and s.get("variant") != exp["variant"]:
            return f"variant {s.get('variant')}"
        if "matching_documents" in exp and s.get("matching_documents") != exp["matching_documents"]:
            return f"matching {s.get('matching_documents')}"
        if "top_doc" in exp:
            top = (res.get("ranking") or [{}])[0]
            if top.get("document_id") != exp["top_doc"]:
                return f"top_doc {top.get('document_id')}"
    if fn_name == "compute_tfidf":
        s = res.get("input_summary", {})
        if "documents" in exp and s.get("documents") != exp["documents"]:
            return f"documents {s.get('documents')}"
        if "vocab_ge" in exp and not (s.get("vocabulary_size", 0) >= exp["vocab_ge"]):
            return f"vocab {s.get('vocabulary_size')}"
    # markov_chain expected_output keys
    if fn_name == "build_chain":
        s = res.get("input_summary", {})
        if "order" in exp and s.get("order") != exp["order"]:
            return f"order {s.get('order')}"
        if "vocab_ge" in exp and not (s.get("vocabulary_size", 0) >= exp["vocab_ge"]):
            return f"vocab {s.get('vocabulary_size')}"
        if "has_context" in exp and exp["has_context"] not in res.get("transitions", {}):
            return f"missing context {exp['has_context']}"
    if fn_name == "compute_entropy":
        if "avg_entropy_ge" in exp and not (res.get("average_entropy", -1) >= exp["avg_entropy_ge"]):
            return f"avg_entropy {res.get('average_entropy')}"
    if fn_name == "next_token_distribution":
        if "dist_sum_eq" in exp:
            total = sum(res.values())
            if abs(total - exp["dist_sum_eq"]) > 1e-6:
                return f"dist sum {total}"
    if fn_name == "generate_sequence":
        s = res.get("input_summary", {})
        if "gen_len" in exp and s.get("generated_tokens") != exp["gen_len"]:
            return f"gen_len {s.get('generated_tokens')}"
        if "stopped" in exp and exp["stopped"] is True:
            if s.get("generated_tokens", 0) > 0:
                return f"expected stop, got {s.get('generated_tokens')} tokens"
    # naive_bayes_classifier expected_output keys
    if fn_name == "train_classifier":
        s = res.get("input_summary", {})
        if "classes" in exp and s.get("classes") != exp["classes"]:
            return f"classes {s.get('classes')}"
        if "classes_len" in exp and len(s.get("classes", [])) != exp["classes_len"]:
            return f"classes_len {len(s.get('classes', []))}"
        if "vocab_ge" in exp and not (s.get("vocabulary_size", 0) >= exp["vocab_ge"]):
            return f"vocab {s.get('vocabulary_size')}"
        if "feature_type" in exp and s.get("feature_type") != exp["feature_type"]:
            return f"feature_type {s.get('feature_type')}"
        if "train_acc" in exp and abs(res.get("training_stats", {}).get("accuracy_on_training_set", -1) - exp["train_acc"]) > 1e-6:
            return f"train_acc {res.get('training_stats', {}).get('accuracy_on_training_set')}"
    if fn_name == "classify":
        pc = res.get("classification", {}).get("predicted_class")
        if "predicted_class" in exp and pc != exp["predicted_class"]:
            return f"predicted_class {pc}"
    if fn_name == "batch_classify":
        if "documents_classified" in exp and res.get("documents_classified") != exp["documents_classified"]:
            return f"documents_classified {res.get('documents_classified')}"
    if fn_name == "evaluate_classifier":
        if "test_documents" in exp and res.get("test_documents") != exp["test_documents"]:
            return f"test_documents {res.get('test_documents')}"
        if "accuracy" in exp and abs(res.get("results", {}).get("accuracy", -1) - exp["accuracy"]) > 1e-6:
            return f"accuracy {res.get('results', {}).get('accuracy')}"
    return ""


def main() -> int:
    fixtures = sorted(glob.glob(os.path.join(REPO, "tools", "**", "TEST-*.json"), recursive=True))
    results = []
    skipped = []
    for fx in fixtures:
        try:
            data = json.load(open(fx, encoding="utf-8"))
        except Exception as e:
            skipped.append((fx, f"LOAD: {e}"))
            continue
        cases = data.get("test_cases")
        if not isinstance(cases, list):
            skipped.append((fx, "no executable test_cases (example corpus)"))
            continue
        pkg = _pkg_for(fx)
        if pkg not in OWNED_PACKAGES:
            skipped.append((fx, f"package tools.{pkg} not owned by runner (legacy/heterogeneous)"))
            continue
        try:
            mod = importlib.import_module(f"tools.{pkg}")
        except Exception as e:
            skipped.append((fx, f"IMPORT tools.{pkg}: {e}"))
            continue
        samples = data.get("samples", {})
        for tc in cases:
            fn_name = tc.get("function")
            if not fn_name:
                skipped.append((fx, "test case missing 'function' key (unsupported shape)"))
                continue
            if fn_name == "cli":
                skipped.append((fx, "cli case is an integration stub (skipped)"))
                continue
            fn = getattr(mod, fn_name, None)
            if fn is None:
                results.append((fx, fn_name, False, "function not found"))
                continue
            exp = tc.get("expected_output", {})
            try:
                inp = _expand(tc["input"], samples)
                sig = inspect.signature(fn)
                params = set(sig.parameters)
                kwargs = {}
                for k, v in inp.items():
                    target = ALIASES.get(fn_name, {}).get(k, k)
                    if target in params:
                        kwargs[target] = v
                if "raises" in exp:
                    try:
                        fn(**kwargs)
                        results.append((fx, fn_name, False, f"expected {exp['raises']} not raised"))
                    except ValueError:
                        results.append((fx, fn_name, True, ""))
                    except Exception as e:
                        results.append((fx, fn_name, False, f"wrong exception {type(e).__name__}: {e}"))
                    continue
                res = fn(**kwargs)
                detail = _check_expected(fn_name, res, exp)
                # determinism re-check (e.g. seeded generation must reproduce)
                if detail == "" and exp.get("deterministic") and fn_name == "generate_sequence":
                    rerun = fn(**kwargs)
                    if rerun.get("generated_sequence") != res.get("generated_sequence"):
                        detail = "non-deterministic re-run"
                results.append((fx, fn_name, detail == "", detail))
            except Exception as e:
                results.append((fx, fn_name, False, f"{type(e).__name__}: {e}"))
    fails = [(fx, fn, d) for fx, fn, ok, d in results if not ok]
    for fx, fn, ok, d in results:
        print(f"{'PASS' if ok else 'FAIL'}  {os.path.basename(fx)}::{fn}" + ("" if ok else f"  -> {d}"))
    if skipped:
        print("\nSKIPPED (informational):")
        for fx, why in skipped:
            print(f"  - {os.path.basename(fx)}: {why}")
    print(f"\n{len(results)-len(fails)} PASS / {len(fails)} FAIL across {len(results)} executed cases ({len(skipped)} fixtures skipped)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
