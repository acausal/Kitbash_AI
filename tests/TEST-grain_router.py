"""
TEST-grain_router.py — contract test for GrainRouter.search_grains.

Run (from repo root):  .venv\Scripts\activate && python tests/TEST-grain_router.py

Locks in the behavior that moved the socket YELLOW (concept-overlap fix):
  - query-conditioned ranking: a grain whose `text` overlaps the query concepts
    must outrank a grain whose `text` does not (this is the fix — before, the
    router scored query-independently).
  - returns List[Tuple[str, float]] sorted by score descending.
  - empty-safe when nothing overlaps.
  - recent_grains graph boost raises a grain's score.

Synthetic grains injected in-memory (no disk dependency). No pytest.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grain_router import GrainRouter


def _router_with(grains, graph=None):
    """Build a GrainRouter and inject synthetic grains in-memory."""
    r = GrainRouter(cartridges_dir="./cartridges")
    r.grains = grains
    r.grain_graph = graph or {}
    return r


def main() -> int:
    # Two grains: one about "photosynthesis", one about "chess" (unrelated).
    grains = {
        "sg_aaa": {"text": "photosynthesis converts light into glucose in plants",
                   "confidence": 0.5},
        "sg_bbb": {"text": "chess is a strategic board game with pieces",
                   "confidence": 0.5},
    }

    # 1. query-conditioned ranking: photosynthesis query must rank sg_aaa first
    r = _router_with(grains)
    res = r.search_grains(["photosynthesis", "plants"])
    assert isinstance(res, list), "search_grains must return a list"
    assert res, "expected at least one ranked result"
    assert all(isinstance(t, tuple) and len(t) == 2 for t in res), "items must be (id, score)"
    top_id, top_score = res[0]
    assert top_id == "sg_aaa", f"photosynthesis query should rank sg_aaa first, got {top_id}"
    print(f"[1] query-conditioned ranking: OK (top={top_id}, score={top_score:.3f})")

    # 2. unrelated query ranks the other grain first (still query-conditioned)
    res2 = r.search_grains(["chess", "board"])
    assert res2[0][0] == "sg_bbb", f"chess query should rank sg_bbb first, got {res2[0][0]}"
    print(f"[2] unrelated query re-ranks: OK (top={res2[0][0]})")

    # 3. empty-safe: no overlap -> empty list, no crash
    res3 = r.search_grains(["xyzqwv", "gibberish"])
    assert isinstance(res3, list)
    # grains with no text overlap fall back to confidence (0.5) so may still return;
    # assert it does not raise and is sorted descending
    if res3:
        scores = [s for _, s in res3]
        assert scores == sorted(scores, reverse=True), "results must be score-descending"
    print(f"[3] no-overlap safe: OK (returned {len(res3)} results, sorted)")

    # 4. recent_grains graph boost: a grain adjacent to a recent grain scores higher
    grains2 = {
        "sg_x": {"text": "machine learning model training", "confidence": 0.5},
        "sg_y": {"text": "machine learning model training", "confidence": 0.5},  # identical text
    }
    # sg_y is adjacent to recent grain sg_x via graph
    graph = {"sg_y": {"sg_x"}}
    r2 = _router_with(grains2, graph)
    base = r2.search_grains(["machine", "learning"])
    scores = {gid: sc for gid, sc in base}
    # Without recent boost both equal; with recent=[sg_x], sg_y should gain +0.20
    boosted = r2.search_grains(["machine", "learning"], recent_grains=["sg_x"])
    boosted_scores = {gid: sc for gid, sc in boosted}
    assert boosted_scores["sg_y"] > scores["sg_y"], "graph boost should raise sg_y"
    assert abs((boosted_scores["sg_y"] - scores["sg_y"]) - 0.20) < 1e-9, \
        f"graph boost should be +0.20, got {boosted_scores['sg_y'] - scores['sg_y']}"
    print(f"[4] graph boost: OK (sg_y {scores['sg_y']:.3f} -> {boosted_scores['sg_y']:.3f})")

    print("\nRESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\nRESULT: FAIL — {e}")
        sys.exit(1)
