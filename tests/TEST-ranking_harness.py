"""
TEST-ranking_harness.py

Ranking evaluation harness for Kitbash retrieval-as-sorting.

Purpose: convert "appears to work" into numbers. Generates a synthetic corpus
with planted ground truth, hands (query, candidates) to rankers through a
sealed boundary, and scores the returned orderings with objective ranking
metrics. Ships with dumb baselines that any justified ranker must beat.

Design principles (anti-loophole):
  1. SEALED BOUNDARY. Rankers receive only (query_text, candidates). Relevance
     labels live in a private structure the ranker never sees. Candidate
     metadata is whitelisted and rebuilt fresh per query — no label smuggling.
  2. NO POSITIONAL LEAKAGE. Candidates are shuffled per-query with a derived
     RNG before crossing the boundary, so dataset construction order carries
     no signal.
  3. PERMUTATION OR DEATH. A ranking must be an exact permutation of the
     candidate ids handed over. Drops, additions, or duplicates hard-fail
     that ranker for the run.
  4. DETERMINISM & PROVENANCE. One master seed derives all randomness. Every
     results row records seed, dataset hash, harness version, and config, so
     any number in the log is reproducible.
  5. TRAPPED DATASET. Every baseline has a planted failure mode:
       - synonym gap: queries phrase concepts with synonym tokens the true
         answer does not share, while LEXICAL TRAP distractors share more
         surface tokens with the query than the answer does (caps TF-IDF);
       - POPULARITY TRAPS: wrong candidates with inflated hit_count
         (caps hit-count ranking);
       - RECENCY TRAPS: wrong candidates planted as most-recent
         (caps recency ranking).
     A ranker that beats all baselines is doing something none of the cheap
     signals explain.
  6. HOLDOUT DISCIPLINE. --holdout evaluates on a differently-derived seed.
     Do not tune against holdout results; they exist to catch overfitting to
     the dev seed.

Run:
  python TEST-ranking_harness.py --selfcheck          # prove the harness works
  python TEST-ranking_harness.py                      # baselines on dev seed
  python TEST-ranking_harness.py --rankers all        # + Kitbash adapters
  python TEST-ranking_harness.py --holdout            # final numbers only

Pure stdlib. No third-party dependencies, no network, no services.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

HARNESS_VERSION = "1.0.0"

# Metadata keys a ranker is allowed to see. Anything else is stripped.
META_WHITELIST = ("created_at", "hit_count")


# ============================================================================
# DATA MODEL
# ============================================================================

@dataclass(frozen=True)
class Candidate:
    """What a ranker is allowed to see about one candidate."""
    cand_id: str
    text: str
    meta: Dict[str, float]  # whitelisted keys only


@dataclass(frozen=True)
class QueryCase:
    """What a ranker is allowed to see about one query."""
    query_id: str
    query_text: str


@dataclass
class Dataset:
    """Public cases plus PRIVATE labels. Labels never cross the boundary."""
    seed_label: str
    cases: List[QueryCase]
    candidates: Dict[str, List[Candidate]]        # query_id -> candidates
    _relevant: Dict[str, str] = field(repr=False, default_factory=dict)
    dataset_hash: str = ""

    def relevant_id(self, query_id: str) -> str:
        """Evaluator-only access to ground truth."""
        return self._relevant[query_id]


# ============================================================================
# DATASET BUILDER
# ============================================================================

def _derive_seed(master_seed: int, purpose: str) -> int:
    """Independent, reproducible sub-seeds; no accidental stream coupling."""
    h = hashlib.sha256(f"{master_seed}:{purpose}".encode()).hexdigest()
    return int(h[:12], 16)


def build_dataset(
    master_seed: int,
    n_queries: int = 200,
    n_candidates: int = 50,
    fact_len: int = 8,
    query_len: int = 4,
    synonym_rate: float = 0.5,
    seed_label: str = "dev",
) -> Dataset:
    """
    Build a planted-answer ranking dataset.

    Vocabulary has paired synonym tokens (qform_i <-> dform_i). Facts are
    written in d-forms; queries describe their target fact partly in q-forms
    (controlled by synonym_rate), creating a semantic-vs-lexical gap. Traps:

      lexical trap : wrong candidate containing the query's literal tokens
      popularity   : wrong candidate with hit_count ~50x the answer's
      recency      : wrong candidate with the newest created_at in the pool
    """
    rng = random.Random(_derive_seed(master_seed, f"dataset:{seed_label}"))

    n_pairs = 400
    qform = [f"q{i:04d}" for i in range(n_pairs)]     # query-side synonyms
    dform = [f"d{i:04d}" for i in range(n_pairs)]     # document-side synonyms
    filler = [f"f{i:04d}" for i in range(600)]        # shared neutral tokens

    def make_fact(concept_ids: Sequence[int]) -> str:
        toks = [dform[c] for c in concept_ids]
        toks += rng.sample(filler, fact_len - len(toks))
        rng.shuffle(toks)
        return " ".join(toks)

    cases: List[QueryCase] = []
    cand_map: Dict[str, List[Candidate]] = {}
    relevant: Dict[str, str] = {}

    for qi in range(n_queries):
        query_id = f"query_{seed_label}_{qi:04d}"
        concept_ids = rng.sample(range(n_pairs), query_len)

        # Query text: each concept rendered in q-form with prob synonym_rate,
        # else d-form. q-form tokens do NOT appear in the true answer.
        q_tokens, answer_concepts = [], []
        for c in concept_ids:
            if rng.random() < synonym_rate:
                q_tokens.append(qform[c])
            else:
                q_tokens.append(dform[c])
            answer_concepts.append(c)
        query_text = " ".join(q_tokens)

        pool: List[Tuple[str, str, float, int]] = []  # (id, text, created, hits)

        def base_hits() -> int:
            return rng.randint(0, 8)

        # True answer: middle-of-the-road on every non-content signal.
        ans_id = f"{query_id}_ans"
        pool.append((ans_id, make_fact(answer_concepts),
                     rng.uniform(0.2, 0.8), base_hits()))

        # Lexical trap: contains the query's literal tokens, wrong answer.
        trap_text_toks = q_tokens + rng.sample(filler, fact_len - len(q_tokens))
        rng.shuffle(trap_text_toks)
        pool.append((f"{query_id}_lex", " ".join(trap_text_toks),
                     rng.uniform(0.2, 0.8), base_hits()))

        # Popularity trap: unrelated, massively "used".
        pop_ids = rng.sample(range(n_pairs), query_len)
        pool.append((f"{query_id}_pop", make_fact(pop_ids),
                     rng.uniform(0.2, 0.8), rng.randint(200, 500)))

        # Recency trap: unrelated, newest item in the pool.
        rec_ids = rng.sample(range(n_pairs), query_len)
        pool.append((f"{query_id}_rec", make_fact(rec_ids),
                     rng.uniform(0.95, 1.0), base_hits()))

        # Near-miss distractors: share some concepts with the answer.
        n_near = max(2, n_candidates // 10)
        for d in range(n_near):
            shared = rng.sample(concept_ids, rng.randint(1, query_len - 1))
            extra = rng.sample(range(n_pairs), query_len - len(shared))
            pool.append((f"{query_id}_near{d}", make_fact(shared + extra),
                         rng.uniform(0.2, 0.8), base_hits()))

        # Random distractors to fill the pool.
        while len(pool) < n_candidates:
            ids = rng.sample(range(n_pairs), query_len)
            pool.append((f"{query_id}_rnd{len(pool)}", make_fact(ids),
                         rng.uniform(0.2, 0.8), base_hits()))

        cands = [
            Candidate(cid, text, {"created_at": round(created, 6),
                                  "hit_count": float(hits)})
            for cid, text, created, hits in pool
        ]

        cases.append(QueryCase(query_id, query_text))
        cand_map[query_id] = cands
        relevant[query_id] = ans_id

    ds = Dataset(seed_label=seed_label, cases=cases,
                 candidates=cand_map, _relevant=relevant)
    ds.dataset_hash = _hash_dataset(ds)
    _assert_no_leak(ds)
    return ds


def _hash_dataset(ds: Dataset) -> str:
    payload = {
        "cases": [(c.query_id, c.query_text) for c in ds.cases],
        "cands": {qid: [(c.cand_id, c.text, sorted(c.meta.items()))
                        for c in cl] for qid, cl in ds.candidates.items()},
        "labels": sorted(ds._relevant.items()),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _assert_no_leak(ds: Dataset) -> None:
    """Structural guarantee that labels cannot ride along with candidates."""
    for cl in ds.candidates.values():
        for c in cl:
            illegal = set(c.meta) - set(META_WHITELIST)
            if illegal:
                raise AssertionError(f"Non-whitelisted meta keys: {illegal}")
    # The answer id is derivable from its suffix only inside this module;
    # rankers receive ids AFTER anonymization in evaluate(). Nothing to do
    # here beyond meta checks — see _anonymize().


# ============================================================================
# RANKER CONTRACT
# ============================================================================

class Ranker:
    """
    Contract: rank() returns candidate ids, best first, as an EXACT
    permutation of the ids handed in. Ties must be resolved internally and
    deterministically (convention: sort by (-score, cand_id)).
    """
    name = "abstract"

    def rank(self, query_text: str, candidates: List[Candidate]) -> List[str]:
        raise NotImplementedError


class RankerError(RuntimeError):
    pass


def _validate_permutation(returned: List[str], expected_ids: List[str],
                          ranker_name: str) -> None:
    if sorted(returned) != sorted(expected_ids):
        missing = set(expected_ids) - set(returned)
        extra = set(returned) - set(expected_ids)
        dupes = [k for k, v in Counter(returned).items() if v > 1]
        raise RankerError(
            f"[{ranker_name}] ranking is not a permutation of candidates "
            f"(missing={len(missing)}, extra={len(extra)}, dupes={len(dupes)})"
        )


# ============================================================================
# BASELINES — the bar to clear
# ============================================================================

def _by_score(scored: List[Tuple[str, float]]) -> List[str]:
    return [cid for cid, _ in sorted(scored, key=lambda x: (-x[1], x[0]))]


class RandomRanker(Ranker):
    name = "random"

    def __init__(self, seed: int):
        self._rng = random.Random(seed)

    def rank(self, query_text, candidates):
        ids = [c.cand_id for c in candidates]
        self._rng.shuffle(ids)
        return ids


class RecencyRanker(Ranker):
    name = "recency"

    def rank(self, query_text, candidates):
        return _by_score([(c.cand_id, c.meta.get("created_at", 0.0))
                          for c in candidates])


class HitCountRanker(Ranker):
    """Popularity ranking. Structurally what GrainRouter.search_grains does
    today (query-independent intrinsic score), so this baseline doubles as
    its stand-in until the live adapter is wired."""
    name = "hit_count"

    def rank(self, query_text, candidates):
        return _by_score([(c.cand_id, c.meta.get("hit_count", 0.0))
                          for c in candidates])


class TfidfRanker(Ranker):
    """Pure-python TF-IDF + cosine over the per-query candidate pool."""
    name = "tfidf"

    @staticmethod
    def _tf(text: str) -> Counter:
        return Counter(text.split())

    def rank(self, query_text, candidates):
        docs = {c.cand_id: self._tf(c.text) for c in candidates}
        n_docs = len(docs)
        df = Counter()
        for tf in docs.values():
            df.update(tf.keys())
        idf = {t: math.log((1 + n_docs) / (1 + d)) + 1.0
               for t, d in df.items()}

        def vec(tf: Counter) -> Dict[str, float]:
            return {t: f * idf.get(t, math.log(1 + n_docs) + 1.0)
                    for t, f in tf.items()}

        qv = vec(self._tf(query_text))
        qn = math.sqrt(sum(v * v for v in qv.values())) or 1.0

        scored = []
        for cid, tf in docs.items():
            dv = vec(tf)
            dn = math.sqrt(sum(v * v for v in dv.values())) or 1.0
            dot = sum(qv[t] * dv[t] for t in qv.keys() & dv.keys())
            scored.append((cid, dot / (qn * dn)))
        return _by_score(scored)


class OracleRanker(Ranker):
    """SELF-CHECK ONLY. Deliberately constructed with labels to prove the
    metric ceiling is reachable. Never register for real evaluation."""
    name = "_oracle"

    def __init__(self, dataset: Dataset, id_maps: Dict[str, Dict[str, str]]):
        # id_maps: query_id -> {public_id: real_id}; oracle inverts it.
        self._answer_public: Dict[str, str] = {}
        for case in dataset.cases:
            real_ans = dataset.relevant_id(case.query_id)
            inv = {real: pub for pub, real in id_maps[case.query_id].items()}
            self._answer_public[case.query_id] = inv[real_ans]
        self._current_query: Optional[str] = None  # set by evaluator hook

    def rank(self, query_text, candidates):
        ids = [c.cand_id for c in candidates]
        ans = self._answer_public.get(self._current_query)
        if ans in ids:
            ids.remove(ans)
            ids.insert(0, ans)
        return ids


class CheatRankerDrop(Ranker):
    """SELF-CHECK ONLY: returns a broken permutation; must be rejected."""
    name = "_cheat_drop"

    def rank(self, query_text, candidates):
        return [c.cand_id for c in candidates][:-1]


# ============================================================================
# EVALUATION (the sealed boundary lives here)
# ============================================================================

def _anonymize(candidates: List[Candidate], rng: random.Random
               ) -> Tuple[List[Candidate], Dict[str, str]]:
    """
    Shuffle candidate order and replace ids with opaque per-query ids, so
    neither construction order nor id suffixes (_ans/_lex/...) can leak.
    Returns (public candidates, {public_id: real_id}).
    """
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    public, id_map = [], {}
    for i, c in enumerate(shuffled):
        pub_id = f"c{i:03d}"
        id_map[pub_id] = c.cand_id
        public.append(Candidate(pub_id, c.text, dict(c.meta)))
    return public, id_map


def build_id_maps(ds: Dataset, master_seed: int
                  ) -> Dict[str, Dict[str, str]]:
    """Deterministic anonymization maps, shared across all rankers in a run
    so every ranker sees the identical presentation."""
    maps = {}
    for case in ds.cases:
        rng = random.Random(_derive_seed(master_seed, f"anon:{case.query_id}"))
        _, id_map = _anonymize(ds.candidates[case.query_id], rng)
        maps[case.query_id] = id_map
    return maps


def evaluate(ranker: Ranker, ds: Dataset, master_seed: int,
             id_maps: Optional[Dict[str, Dict[str, str]]] = None
             ) -> Dict[str, object]:
    """Run one ranker over the dataset. Returns aggregate + per-query ranks."""
    id_maps = id_maps or build_id_maps(ds, master_seed)
    ranks: List[int] = []
    per_query: Dict[str, int] = {}
    t0 = time.perf_counter()

    for case in ds.cases:
        rng = random.Random(_derive_seed(master_seed, f"anon:{case.query_id}"))
        public, id_map = _anonymize(ds.candidates[case.query_id], rng)

        if isinstance(ranker, OracleRanker):        # self-check hook
            ranker._current_query = case.query_id

        returned = ranker.rank(case.query_text, public)
        _validate_permutation(returned, [c.cand_id for c in public],
                              ranker.name)

        real_ans = ds.relevant_id(case.query_id)
        rank = next(i + 1 for i, pub in enumerate(returned)
                    if id_map[pub] == real_ans)
        ranks.append(rank)
        per_query[case.query_id] = rank

    elapsed = time.perf_counter() - t0
    n = len(ranks)
    agg = {
        "ranker": ranker.name,
        "n_queries": n,
        "recall@1": sum(r <= 1 for r in ranks) / n,
        "recall@3": sum(r <= 3 for r in ranks) / n,
        "recall@5": sum(r <= 5 for r in ranks) / n,
        "recall@10": sum(r <= 10 for r in ranks) / n,
        "mrr": sum(1.0 / r for r in ranks) / n,
        "mean_rank": sum(ranks) / n,
        "eval_seconds": round(elapsed, 3),
    }
    return {"aggregate": agg, "per_query": per_query}


def paired_bootstrap(per_query_a: Dict[str, int], per_query_b: Dict[str, int],
                     seed: int, n_boot: int = 2000) -> Dict[str, float]:
    """Paired bootstrap on MRR delta (a - b) plus win/tie/loss counts."""
    qids = sorted(set(per_query_a) & set(per_query_b))
    rr_a = [1.0 / per_query_a[q] for q in qids]
    rr_b = [1.0 / per_query_b[q] for q in qids]
    deltas = [a - b for a, b in zip(rr_a, rr_b)]
    rng = random.Random(seed)
    n = len(deltas)
    boots = []
    for _ in range(n_boot):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(sample) / n)
    boots.sort()
    return {
        "mrr_delta": sum(deltas) / n,
        "ci95_low": boots[int(0.025 * n_boot)],
        "ci95_high": boots[int(0.975 * n_boot)],
        "wins": sum(d > 0 for d in deltas),
        "ties": sum(d == 0 for d in deltas),
        "losses": sum(d < 0 for d in deltas),
    }


# ============================================================================
# RESULTS LOG
# ============================================================================

def write_result(path: str, row: Dict) -> None:
    row = dict(row)
    row["harness_version"] = HARNESS_VERSION
    row["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


# ============================================================================
# ADAPTER LOADING (TEST- prefix breaks normal import; load by path)
# ============================================================================

def load_kitbash_adapters(harness_module) -> List[Ranker]:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "TEST-ranking_adapters_kitbash.py")
    if not os.path.exists(path):
        print("  [skip] TEST-ranking_adapters_kitbash.py not found")
        return []
    spec = importlib.util.spec_from_file_location("kitbash_adapters", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod.get_rankers(harness_module)
    except Exception as e:
        print(f"  [skip] Kitbash adapters unavailable: {type(e).__name__}: {e}")
        return []


# ============================================================================
# SELF-CHECK — the harness proves itself before it judges anything
# ============================================================================

def selfcheck() -> int:
    print("=== Harness self-check ===")
    seed = 99991
    ds = build_dataset(seed, n_queries=40, n_candidates=25, seed_label="selfcheck")
    id_maps = build_id_maps(ds, seed)
    failures = 0

    def check(label: str, ok: bool, detail: str = ""):
        nonlocal failures
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" +
              (f" — {detail}" if detail and not ok else ""))
        failures += 0 if ok else 1

    # 1. Determinism: same seed -> same dataset hash.
    ds2 = build_dataset(seed, n_queries=40, n_candidates=25, seed_label="selfcheck")
    check("dataset determinism", ds.dataset_hash == ds2.dataset_hash)

    # 2. Oracle reaches the ceiling: proves scoring is sound.
    oracle = OracleRanker(ds, id_maps)
    res = evaluate(oracle, ds, seed, id_maps)
    check("oracle MRR == 1.0", abs(res["aggregate"]["mrr"] - 1.0) < 1e-12,
          f"got {res['aggregate']['mrr']}")

    # 3. Cheater rejected: broken permutations cannot score.
    try:
        evaluate(CheatRankerDrop(), ds, seed, id_maps)
        check("broken permutation rejected", False, "no exception raised")
    except RankerError:
        check("broken permutation rejected", True)

    # 4. Random ranker lands near chance (MRR for n=25 ≈ 0.15 ± noise).
    res_r = evaluate(RandomRanker(seed=7), ds, seed, id_maps)
    check("random near chance", 0.03 < res_r["aggregate"]["mrr"] < 0.35,
          f"mrr={res_r['aggregate']['mrr']:.3f}")

    # 5. Traps bite: popularity ranker must place the popularity trap first
    #    (query-independent scores put hit_count=200+ on top), so its
    #    recall@1 must be ~0. Same logic pins recency.
    res_h = evaluate(HitCountRanker(), ds, seed, id_maps)
    check("popularity trap bites hit_count", res_h["aggregate"]["recall@1"] < 0.05,
          f"recall@1={res_h['aggregate']['recall@1']:.3f}")
    res_c = evaluate(RecencyRanker(), ds, seed, id_maps)
    check("recency trap bites recency", res_c["aggregate"]["recall@1"] < 0.05,
          f"recall@1={res_c['aggregate']['recall@1']:.3f}")

    # 6. Synonym gap caps TF-IDF: strong but visibly below oracle.
    res_t = evaluate(TfidfRanker(), ds, seed, id_maps)
    check("tfidf above random", res_t["aggregate"]["mrr"] > res_r["aggregate"]["mrr"])
    check("tfidf below ceiling", res_t["aggregate"]["mrr"] < 0.999,
          f"mrr={res_t['aggregate']['mrr']:.3f}")

    # 7. Anonymization: public ids carry no answer-identifying suffixes.
    sample_map = id_maps[ds.cases[0].query_id]
    check("ids anonymized", all(p.startswith("c") and p[1:].isdigit()
                                for p in sample_map))

    print(f"\n{'SELF-CHECK PASSED' if failures == 0 else f'{failures} FAILURE(S)'}")
    return 1 if failures else 0


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description="Kitbash ranking harness")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--candidates", type=int, default=50)
    ap.add_argument("--rankers", default="baselines",
                    help="'baselines', 'all' (adds Kitbash adapters), or CSV of names")
    ap.add_argument("--holdout", action="store_true",
                    help="evaluate on holdout-derived seed; DO NOT tune on this")
    ap.add_argument("--results", default="TEST-harness_results.jsonl")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()

    label = "holdout" if args.holdout else "dev"
    seed = _derive_seed(args.seed, label)
    ds = build_dataset(seed, args.queries, args.candidates, seed_label=label)
    id_maps = build_id_maps(ds, seed)
    print(f"Dataset: {label} seed={args.seed} hash={ds.dataset_hash} "
          f"({args.queries} queries x {args.candidates} candidates)")
    if args.holdout:
        print("HOLDOUT RUN — record the number, do not tune against it.\n")

    pool: Dict[str, Ranker] = {r.name: r for r in [
        RandomRanker(seed=_derive_seed(seed, "random_ranker")),
        RecencyRanker(), HitCountRanker(), TfidfRanker(),
    ]}
    if args.rankers in ("all",):
        for r in load_kitbash_adapters(sys.modules[__name__]):
            pool[r.name] = r
        selected = list(pool.values())
    elif args.rankers == "baselines":
        selected = list(pool.values())
    else:
        wanted = [w.strip() for w in args.rankers.split(",")]
        for r in load_kitbash_adapters(sys.modules[__name__]):
            pool[r.name] = r
        missing = [w for w in wanted if w not in pool]
        if missing:
            print(f"Unknown rankers: {missing}. Available: {sorted(pool)}")
            return 1
        selected = [pool[w] for w in wanted]

    results = {}
    header = f"{'ranker':<16}{'R@1':>7}{'R@3':>7}{'R@5':>7}{'R@10':>7}{'MRR':>8}{'meanRk':>8}"
    print(header)
    print("-" * len(header))
    for ranker in selected:
        try:
            res = evaluate(ranker, ds, seed, id_maps)
        except RankerError as e:
            print(f"{ranker.name:<16}  DISQUALIFIED: {e}")
            continue
        a = res["aggregate"]
        results[ranker.name] = res
        print(f"{a['ranker']:<16}{a['recall@1']:>7.3f}{a['recall@3']:>7.3f}"
              f"{a['recall@5']:>7.3f}{a['recall@10']:>7.3f}{a['mrr']:>8.4f}"
              f"{a['mean_rank']:>8.2f}")
        write_result(args.results, {
            "run_label": label, "master_seed": args.seed,
            "dataset_hash": ds.dataset_hash,
            "config": {"queries": args.queries, "candidates": args.candidates},
            **a,
        })

    # Paired comparisons: every non-baseline vs every baseline.
    baselines = {"random", "recency", "hit_count", "tfidf"}
    contenders = [n for n in results if n not in baselines]
    if contenders:
        print("\nPaired bootstrap vs baselines (MRR delta, 95% CI, W/T/L):")
        for c in contenders:
            for b in sorted(baselines & set(results)):
                cmpres = paired_bootstrap(results[c]["per_query"],
                                          results[b]["per_query"],
                                          seed=_derive_seed(seed, f"boot:{c}:{b}"))
                verdict = ("BEATS" if cmpres["ci95_low"] > 0 else
                           "LOSES TO" if cmpres["ci95_high"] < 0 else
                           "TIES")
                print(f"  {c} vs {b:<10} Δ={cmpres['mrr_delta']:+.4f} "
                      f"[{cmpres['ci95_low']:+.4f}, {cmpres['ci95_high']:+.4f}] "
                      f"{cmpres['wins']}/{cmpres['ties']}/{cmpres['losses']}  -> {verdict}")
                write_result(args.results, {
                    "run_label": label, "comparison": f"{c}_vs_{b}",
                    "dataset_hash": ds.dataset_hash, **cmpres,
                })
    print(f"\nResults appended to {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
