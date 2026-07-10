"""
TEST-ranking_adapters_kitbash.py

Kitbash-side adapters for TEST-ranking_harness.py. This file is the ONLY
place harness and live system touch; the harness runs fine without it.

Loaded by the harness via importlib (the TEST- prefix blocks normal import).
Contract: expose get_rankers(harness_module) -> List[Ranker]. Adapters that
cannot initialize (missing modules, wrong paths) are skipped with a printed
reason — they never take the harness down.

STATUS OF EACH ADAPTER
  grain_router : WIRED. Honest but with a known caveat (below).
  mtr_pipeline : SKELETON. Deliberately unwired — see the docstring for
                 exactly what is needed. Guessing the call chain from
                 read-only copies is how v6 happened; not repeating that.

CAVEAT on grain_router: as of 2026-07-07, GrainRouter.search_grains accepts
query_concepts and does not use them — scoring is confidence + derivation
bonus + graph boost + CTR (all query-independent). On this harness's planted-
answer task, expect it to perform like the hit_count/random baselines. That
is not an adapter bug; it is the measurement. If the intent is that grains
are a coarse filter and MTR does query-conditioned ranking, the mtr_pipeline
adapter is where the real number will come from.
"""

import sys
from typing import List


# ----------------------------------------------------------------------------
# Adapter 1: GrainRouter (WIRED)
# ----------------------------------------------------------------------------

def _make_grain_router_adapter(h):
    """
    Evaluates GrainRouter.search_grains on harness candidates by injecting
    them as synthetic grains into a throwaway router instance.

    Injection schema is the minimal dict search_grains actually reads:
      confidence  -> neutralized to a constant 0.5 for ALL candidates, so no
                     fabricated signal leaks in; ranking differences can only
                     come from the router's own mechanisms
      delta       -> empty (no derivation bonus for anyone)
    Graph and CTR structures are left empty (no session history exists for
    synthetic candidates). Ties are broken by cand_id for determinism.
    """
    from grain_router import GrainRouter  # requires Kitbash on sys.path

    class GrainRouterRanker(h.Ranker):
        name = "grain_router"

        def __init__(self):
            # Throwaway instance; we bypass disk loading entirely.
            self._router = GrainRouter.__new__(GrainRouter)
            self._router.grains = {}
            self._router.grain_graph = {}
            self._router.grain_ctr = {}

        def rank(self, query_text, candidates):
            self._router.grains = {
                c.cand_id: {"confidence": 0.5, "delta": {}, "text": c.text}
                for c in candidates
            }
            scored = self._router.search_grains(query_text.split())
            order = [gid for gid, _ in scored]
            # search_grains drops zero-score grains; harness demands a full
            # permutation, so append any dropped ids deterministically.
            seen = set(order)
            order += sorted(c.cand_id for c in candidates
                            if c.cand_id not in seen)
            # Deterministic tie-break: search_grains sorts by score only, so
            # equal scores keep dict order. Re-sort stably by (-score, id).
            score_map = dict(scored)
            order.sort(key=lambda cid: (-score_map.get(cid, 0.0), cid))
            return order

    return GrainRouterRanker()


# ----------------------------------------------------------------------------
# Adapter 2: MTR fact-ranking pipeline (SKELETON — deliberately unwired)
# ----------------------------------------------------------------------------

def _make_mtr_pipeline_adapter(h):
    """
    WIRING GUIDE — what this adapter needs before it can exist honestly:

    1. The call that produces a RANKED LIST of fact/grain ids for a query
       inside the live pipeline (the sorting step this harness exists to
       measure). From the read-only audit, candidates are:
         - the MTR-side ranking that feeds fact_ids into
           mtr_grain_bridge.process_mtr_query, or
         - grain_engine.query / cartridge_engine.query InferenceResponse,
           if those carry ordered results.
       Provide the file(s) with that path and this becomes a ~30-line
       adapter: ingest harness candidates as facts, run the query, return
       the ordering.
    2. An ingestion route: how to register N synthetic facts so the pipeline
       can rank them (batch_cartridge_builder? direct registry insertion?).
    3. An ABLATION FLAG once wired: same adapter, MTR output replaced with
       identity/noise, registered as 'mtr_pipeline_ablated'. The delta
       between the two rankers on this harness is the number that answers
       "is the neural core earning its complexity?"

    Until then this raises with instructions rather than fabricating a
    plausible-looking integration. See POSTMORTEM_MTR_v6.md, step 3, for
    why plausible-looking is the enemy.
    """
    raise NotImplementedError(
        "mtr_pipeline adapter unwired: needs the ranked-list call chain and "
        "a fact-ingestion route. See the WIRING GUIDE in "
        "TEST-ranking_adapters_kitbash.py — provide the relevant files and "
        "it is a ~30-line job."
    )


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

def get_rankers(harness_module) -> List:
    """Called by the harness. Returns whatever initializes; skips the rest."""
    rankers = []
    for label, factory in (("grain_router", _make_grain_router_adapter),
                           ("mtr_pipeline", _make_mtr_pipeline_adapter)):
        try:
            rankers.append(factory(harness_module))
        except NotImplementedError as e:
            print(f"  [skip] {label}: {e}")
        except Exception as e:
            print(f"  [skip] {label}: {type(e).__name__}: {e} "
                  f"(is the Kitbash root on sys.path / PYTHONPATH?)")
    return rankers


if __name__ == "__main__":
    print("This file is loaded by TEST-ranking_harness.py (--rankers all). "
          "It does nothing standalone.")
