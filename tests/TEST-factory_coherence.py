#!/usr/bin/env python3
"""
TEST-factory_coherence.py  (SPEC Step 1 / T2 acceptance)

Verifies F2 (no split-brain) and F3 (dream bucket on canonical path) by
constructing the SAME shared instances the factory builds and wiring them
into the adapters -- exactly the code path T2 changed in
query_orchestrator_factory.create_query_orchestrator.

  F2 (grain):   GrainEngine.grain_router is grain_router            (assert a is b)
  F2 (cart):    CartridgeEngine.registry is cartridge_engine_phase3e.registry (assert a is b)
  F3:           dream_bucket_writer is not None on both shared components
                when a bucket dir is supplied

NOTE: the full create_query_orchestrator() cannot boot in this environment
yet -- it unconditionally requires MTR_v5_5_NN (torch) at factory lines
~111-116 with no guard (pre-existing blocker, tracked separately; resolved
when torch is installed / T8). T2's coherence is therefore verified at the
component-wiring level, which is what T2 actually changed. This is ad-hoc
acceptance for T2, NOT the permanent gate (that is T7).

Cartridge/grain loading is pure-Python (no torch), so this runs without torch.

Run:  python TEST-factory_coherence.py
"""

import sys
import logging

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cartridge_loader import CartridgeInferenceEngine
from grain_router import GrainRouter
from dream_bucket import DreamBucketWriter
from grain_engine import GrainEngine
from cartridge_engine import CartridgeEngine


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return ok


def main():
    results = []

    cartridges_dir = "./cartridges"
    dream_bucket_dir = "data/subconscious/dream_bucket"

    # --- Build the shared instances ONCE (mirrors factory Step 1) ---
    dream_bucket_writer = DreamBucketWriter(dream_bucket_dir)
    cartridge_engine_phase3e = CartridgeInferenceEngine(
        cartridges_dir, dream_bucket_writer=dream_bucket_writer
    )
    grain_router = GrainRouter(
        cartridges_dir=cartridges_dir,
        cartridge_engine=cartridge_engine_phase3e,
        dream_bucket_writer=dream_bucket_writer,
    )

    # --- Inject into adapters (mirrors factory Step 2, T2 change) ---
    grain_engine = GrainEngine(cartridges_dir=cartridges_dir, grain_router=grain_router)
    cartridge_engine = CartridgeEngine(
        cartridges_dir=cartridges_dir, cartridge_engine=cartridge_engine_phase3e
    )

    # --- F2: GrainRouter identity (assert a is b) ---
    results.append(check(
        "F2 GrainEngine.grain_router IS the shared GrainRouter (object identity)",
        grain_engine.grain_router is grain_router,
        f"id match={grain_engine.grain_router is grain_router}",
    ))
    results.append(check(
        "F2 shared GrainRouter loaded grains",
        grain_router.total_grains > 0,
        f"total_grains={grain_router.total_grains}",
    ))

    # --- F2: CartridgeInferenceEngine registry identity (assert a is b) ---
    results.append(check(
        "F2 CartridgeEngine.registry IS shared CartridgeInferenceEngine.registry",
        cartridge_engine.registry is cartridge_engine_phase3e.registry,
        f"id match={cartridge_engine.registry is cartridge_engine_phase3e.registry}",
    ))
    results.append(check(
        "F2 adapter did NOT re-load a second .kbc world",
        len(cartridge_engine.cartridges) == 0,
        f"standalone .cartridges={len(cartridge_engine.cartridges)}",
    ))
    results.append(check(
        "F2 shared cartridge registry has facts",
        cartridge_engine_phase3e.registry.get_stats()["total_facts"] > 0,
        f"total_facts={cartridge_engine_phase3e.registry.get_stats()['total_facts']}",
    ))

    # --- F3: dream_bucket_writer threaded into both shared components ---
    results.append(check(
        "F3 dream_bucket_writer not None on shared CartridgeInferenceEngine",
        cartridge_engine_phase3e.dream_bucket_writer is not None,
        f"writer={cartridge_engine_phase3e.dream_bucket_writer}",
    ))
    results.append(check(
        "F3 dream_bucket_writer not None on shared GrainRouter",
        grain_router.dream_bucket_writer is not None,
        f"writer={grain_router.dream_bucket_writer}",
    ))

    # --- Smoke: a real query through the wrapped cartridge engine ---
    from interfaces.inference_engine import InferenceRequest
    resp = cartridge_engine.query(InferenceRequest(user_query="What is photosynthesis?"))
    results.append(check(
        "Smoke: cartridge query returns valid InferenceResponse",
        resp is not None and hasattr(resp, "confidence"),
        f"confidence={resp.confidence:.3f}" if resp else "None",
    ))

    allok = all(results)
    print("=" * 64)
    print(f"T2 factory-coherence: {'ALL PASS' if allok else 'SOME FAILED'}")
    print("=" * 64)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
