"""
TEST-MTR_v6_1_contract.py

Contract test suite for the MTR engine. Every test here corresponds to a
regression that shipped in v6, or a latent bug present since v5.5. If a
future MTR version passes this suite, it has at minimum preserved the
behavioral contract that the orchestrator, grain bridge, and dissonance
pathway depend on.

Run:  python TEST-MTR_v6_1_contract.py
No pytest dependency; plain asserts with a simple runner.
"""

import torch
from MTR_v6_1 import (
    KitbashMTREngine,
    DissonanceSensor,
    LAYER_NAMES,
    DEFAULT_TARGET_LAYER,
)

VOCAB = 1000
D_MODEL = 256
D_STATE = 144  # 12^2


def make_engine(seed: int = 42) -> KitbashMTREngine:
    torch.manual_seed(seed)
    return KitbashMTREngine(vocab_size=VOCAB, d_model=D_MODEL, d_state=D_STATE)


# ----------------------------------------------------------------------------
# Regression: v6 DissonanceSensor KeyError
# Router emitted 'L4_scenario' etc. while the sensor indexed 'L4_intent'.
# ----------------------------------------------------------------------------
def test_snapshot_keys_match_sensor_contract():
    engine = make_engine()
    sensor = DissonanceSensor()
    token_ids = torch.randint(0, VOCAB, (1, 16))

    snapshot = engine.get_epistemic_snapshot(token_ids)
    assert set(snapshot.keys()) == set(LAYER_NAMES), (
        f"Snapshot keys {sorted(snapshot.keys())} != canonical {sorted(LAYER_NAMES)}"
    )

    # The sensor must consume the snapshot without KeyError.
    logits, error, _ = engine(token_ids)
    result = sensor(error, snapshot)
    for key in ('dissonance_active', 'delta_L0_L2', 'delta_L2_L4'):
        assert key in result, f"Sensor output missing '{key}'"


# ----------------------------------------------------------------------------
# Regression: v6 made target_layer a no-op
# All layers shared one representation and the routing weight was discarded,
# so logits were identical regardless of target_layer.
# ----------------------------------------------------------------------------
def test_target_layer_changes_logits():
    engine = make_engine()
    token_ids = torch.randint(0, VOCAB, (1, 12))

    logits_by_layer = {}
    for layer in LAYER_NAMES:
        torch.manual_seed(7)  # identical stochastic conditions per call
        logits, _, _ = engine(token_ids, state=None, target_layer=layer)
        logits_by_layer[layer] = logits

    base = logits_by_layer[DEFAULT_TARGET_LAYER]
    distinct = [
        layer for layer in LAYER_NAMES
        if layer != DEFAULT_TARGET_LAYER
        and not torch.allclose(logits_by_layer[layer], base)
    ]
    assert len(distinct) == len(LAYER_NAMES) - 1, (
        "target_layer must select genuinely distinct per-layer projections; "
        f"only {len(distinct)}/{len(LAYER_NAMES) - 1} layers produced distinct logits"
    )


def test_unknown_target_layer_rejected():
    engine = make_engine()
    token_ids = torch.randint(0, VOCAB, (1, 4))
    for stale_name in ('L2_narrative', 'L4_intent', 'L4_scenario'):
        try:
            engine(token_ids, target_layer=stale_name)
        except ValueError:
            continue
        raise AssertionError(f"Stale layer name '{stale_name}' was silently accepted")


# ----------------------------------------------------------------------------
# Regression: v6 severed the hat -> kappa -> rigidity pathway
# HatKappaMapper feeds kappa per query; higher kappa must sharpen saliences
# (push them away from 0.5, toward 0/1).
# ----------------------------------------------------------------------------
def test_kappa_modulates_salience_sharpness():
    engine = make_engine()
    token_ids = torch.randint(0, VOCAB, (1, 16))

    def mean_extremity(kappa: float) -> float:
        snap = engine.get_epistemic_snapshot(token_ids, kappa=kappa)
        saliences = torch.cat([sal.flatten() for _, sal in snap.values()])
        return (saliences - 0.5).abs().mean().item()

    fluid = mean_extremity(0.2)
    rigid = mean_extremity(5.0)
    assert rigid > fluid, (
        f"kappa must sharpen saliences: extremity at kappa=5.0 ({rigid:.4f}) "
        f"should exceed kappa=0.2 ({fluid:.4f})"
    )


# ----------------------------------------------------------------------------
# Regression: v6 silently switched sigmoid saliences to sum-to-one softmax,
# breaking the bridge's salience > 0.3 extraction gate and the sensor's
# delta_threshold calibration. Saliences must be independent sigmoids.
# ----------------------------------------------------------------------------
def test_salience_regime_is_independent_sigmoid():
    engine = make_engine()
    token_ids = torch.randint(0, VOCAB, (1, 16))
    snap = engine.get_epistemic_snapshot(token_ids)

    # Per-token sum across layers: softmax regime would sum to ~1.0.
    per_layer = [sal.squeeze(-1) for _, sal in snap.values()]  # each (batch, seq)
    total = torch.stack(per_layer, dim=0).sum(dim=0)  # (batch, seq)
    assert (total > 1.5).all(), (
        "Layer saliences appear to sum to ~1 (softmax regime). "
        "Bridge/sensor thresholds require independent sigmoid saliences."
    )
    for _, sal in snap.values():
        assert sal.min() >= 0.0 and sal.max() <= 1.0, "salience out of [0,1]"


# ----------------------------------------------------------------------------
# Latent bug (v5.5 and v6): max_spacing_boost defined but never applied.
# Unbounded strength drives decay_rate -> 0, disabling Ebbinghaus decay
# toward the axiom anchors over long sessions.
# ----------------------------------------------------------------------------
def test_strength_capped_at_max_spacing_boost():
    engine = make_engine()
    cap = engine.mtr.max_spacing_boost
    state = None
    # Long session: many turns so strength accumulation would blow past the
    # cap if unclamped (spacing_factor grows with log1p(delta_t)).
    for _ in range(40):
        token_ids = torch.randint(0, VOCAB, (1, 32))
        _, _, state = engine(token_ids, state=state)
    max_strength = state['strength'].max().item()
    assert max_strength <= cap + 1e-6, (
        f"strength ({max_strength:.3f}) exceeded max_spacing_boost ({cap}); "
        "Ebbinghaus decay toward anchors would degrade over long sessions"
    )


# ----------------------------------------------------------------------------
# Baseline contracts (held by 5.5, must not regress)
# ----------------------------------------------------------------------------
def test_state_persistence_across_turns():
    engine = make_engine()
    state = None
    expected_time = 0
    for _ in range(3):
        token_ids = torch.randint(0, VOCAB, (1, 10))
        _, _, state = engine(token_ids, state=state)
        expected_time += 10
        assert state['time'] == expected_time
    assert 'copent_pos' in state, "CoPENt position must persist in state"


def test_variable_sequence_lengths():
    engine = make_engine()
    for length in (1, 10, 100, 512):
        token_ids = torch.randint(0, VOCAB, (1, length))
        logits, error, state = engine(token_ids)
        assert logits.shape == (1, length, VOCAB)
        assert error.shape == (1, length, 1)


def test_malformed_state_reinitializes():
    engine = make_engine()
    token_ids = torch.randint(0, VOCAB, (1, 8))
    logits, _, state = engine(token_ids, state={'garbage': True})
    assert 'W' in state and state['time'] == 8


def test_state_dict_roundtrip_compatible():
    # Persisted state contains no layer names; a state produced by one engine
    # instance must load into a fresh instance (restart scenario).
    engine_a = make_engine()
    token_ids = torch.randint(0, VOCAB, (1, 10))
    _, _, state = engine_a(token_ids)

    engine_b = make_engine(seed=99)
    _, _, state2 = engine_b(token_ids, state=state)
    assert state2['time'] == 20, "restored state must continue the time counter"


# ----------------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {fn.__name__}\n        {e}")
        except Exception as e:
            failures += 1
            print(f"  ERROR {fn.__name__}\n        {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)
