"""
MTR-Ebbinghaus Hybrid: v6.1 Engine (PRODUCTION)

v6.1 is a corrective release. It restores the proven v5.5 architecture and
retires the v6 additions (LearnedGate, LearnableTemperature, HierarchicalRouter),
which were transplanted from training-dependent literature (see
research_brief_attention_encoding_copent) into a system with no outer training
loop — leaving them frozen at random initialization while silently breaking:
  1. DissonanceSensor (KeyError: router emitted new layer names)
  2. target_layer selection (per-layer projections deleted; weight never applied)
  3. The hat -> kappa -> routing-rigidity pathway (kappa deprecated)
  4. Downstream salience calibration (sigmoid regime -> softmax regime)

Changes vs v5.5:
  - Layer names corrected to EPISTEMOLOGICAL_STACK_SPEC canon (single source
    of truth: LAYER_NAMES below). Both v5.5 and v6 names were off-spec.
  - max_spacing_boost is now actually applied (strength was unbounded, which
    drove decay_rate -> 0 over long sessions, disabling Ebbinghaus decay).
  - Default target_layer updated to spec name.

Deferred (pending sleep-time outer-loop training + evaluation harness):
  - Learned gated fusion of MTR/CoPENt signals (brief section 4)
  - Scheduled/learnable routing temperature (brief section 5)
  - Boundary-gated hierarchical routing (brief section 6.2 — the real design,
    not the v6 cluster invention)

State-dict compatibility: persisted MTR state (W, strength, last_seen, time,
copent_pos) contains no layer names and loads unchanged from v5.5/v6.

Author: Kitbash Team
Date: July 7, 2026
"""

import torch
import torch.nn as nn
import math
from typing import Tuple, Optional, Dict


# ============================================================================
# CANONICAL EPISTEMIC LAYER NAMES (EPISTEMOLOGICAL_STACK_SPEC)
# ============================================================================
# Single source of truth. Downstream consumers (mtr_grain_bridge, orchestrators)
# should import this rather than hardcoding strings.

LAYER_NAMES = [
    'L0_ground_truth',  # Immutable facts (ground truth)
    'L1_axiomatic',     # Crystallized grains, confidence-scored observations
    'L2_heuristic',     # Working theory: MTR weights, phantoms, co-occurrence
    'L3_context',       # Query context, conversation frame (session-scoped)
    'L4_hat',           # Behavioral mode (ANALYTICAL, CREATIVE, ...)
    'L5_session',       # Long-term scenario state, user model
]

DEFAULT_TARGET_LAYER = 'L2_heuristic'


# ============================================================================
# COMPONENT 1: SPARSE CONTEXTUAL COUNTER (CoPENt)
# ============================================================================

class SparseContextualCounter(nn.Module):
    """
    CoPENt: Structural positional encoding via sinusoids.

    Detects topic breaks and generates position-dependent sinusoid embeddings.
    Replaces fixed-size positional embedding with dynamic, infinite-context encoding.
    """

    def __init__(self, d_model: int, threshold: float = 0.85):
        super().__init__()
        assert d_model % 2 == 0, f"d_model must be even for sinusoid encoding, got {d_model}"

        self.d_model = d_model
        self.threshold = threshold
        self.gate = nn.Linear(d_model, 1)

        # Sinusoidal frequency basis (must be d_model/2 for sin+cos concatenation)
        inv_freq = 1.0 / (10000 ** (torch.arange(0, d_model, 2).float() / d_model))
        self.register_buffer("inv_freq", inv_freq)

    def forward(
        self,
        x: torch.Tensor,
        last_pos: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, seq_len, d_model) - input embeddings
            last_pos: (batch, 1) - last structural position from previous call

        Returns:
            pos_emb: (batch, seq_len, d_model) - positional embeddings
            new_last_pos: (batch, 1) - final position for next call
        """
        batch, seq_len, d_model = x.shape
        device = x.device
        dtype = x.dtype

        # Detect structural breaks (topic shifts, speaker changes)
        raw_gate = torch.sigmoid(self.gate(x))  # (batch, seq_len, 1)

        # Sparse gating: only pass tokens that exceed threshold
        sparse_gate = torch.where(
            raw_gate > self.threshold,
            raw_gate,
            torch.zeros_like(raw_gate)
        )

        # Initialize position counter if first call
        if last_pos is None:
            last_pos = torch.zeros(batch, 1, device=device, dtype=dtype)

        # Accumulate structural positions: p[t] = last_pos + sum(sparse_gate[0:t])
        p = last_pos.unsqueeze(1) + torch.cumsum(sparse_gate, dim=1)  # (batch, seq_len, 1)
        new_last_pos = p[:, -1:, :].squeeze(-1)  # (batch, 1)

        # Generate sinusoid positional embeddings (no hard size limit)
        positions = p.squeeze(-1)  # (batch, seq_len)

        # Outer product: positions x frequencies
        sinusoid_inp = torch.einsum('bs,f->bsf', positions, self.inv_freq)

        # Interleave sin and cos for full d_model
        pos_emb = torch.cat(
            [torch.sin(sinusoid_inp), torch.cos(sinusoid_inp)],
            dim=-1
        )  # (batch, seq_len, d_model)

        return pos_emb, new_last_pos


# ============================================================================
# COMPONENT 2: MTR-EBBINGHAUS LAYER (Core Compute Engine)
# ============================================================================

class MTREbbinghausLayer(nn.Module):
    """
    Monarch-TTT with Time-Aware Power-Law Decay.

    - Monarch: Sparse block-diagonal matrix structure
    - TTT: Test-Time Training updates weights during inference
    - Ebbinghaus: Memory decay with time + strength components
    """

    def __init__(self, d_model: int, d_state: int = 128, lr: float = 0.1, base_decay: float = 0.05):
        super().__init__()
        self.d_model = d_model
        self.d_state = d_state
        self.lr = lr
        self.base_decay = base_decay
        self.max_spacing_boost = 10.0  # Cap on accumulated strength (v6.1: now enforced)

        # Require perfect square, no padding
        sqrt_n = int(math.sqrt(d_state))
        assert sqrt_n * sqrt_n == d_state, \
            f"d_state must be perfect square (64, 100, 121, 144, ...), got {d_state}"
        self.sqrt_n = sqrt_n

        # Projections: embed -> state space
        self.k_proj = nn.Linear(d_model, self.d_state, bias=False)
        self.v_proj = nn.Linear(d_model, self.d_state, bias=False)
        self.selection_gate = nn.Linear(d_model, 1)

        # Base weights (axiom anchors): never learned, only decay toward them
        w_init = torch.eye(self.sqrt_n).repeat(self.sqrt_n, 1, 1)
        self.register_buffer("W1_init", w_init)
        self.register_buffer("W2_init", w_init)

        # Output projection: state space -> embedding
        self.out_proj = nn.Linear(self.d_state, d_model)

    def forward(
        self,
        x: torch.Tensor,
        state: Optional[dict] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, dict]:
        """
        Args:
            x: (batch, seq_len, d_model) - input embeddings
            state: Optional dict with keys: W, strength, last_seen, time

        Returns:
            output: (batch, seq_len, d_model) - processed representations
            error_signal: (batch, seq_len, 1) - TTT prediction error
            new_state: Updated state dict for next call
        """
        batch, seq_len, d_model = x.shape
        device = x.device
        dtype = x.dtype

        # Initialize or restore state
        if state is None or 'W' not in state:
            w1 = self.W1_init.clone().to(dtype=dtype, device=device).repeat(batch, 1, 1, 1)
            w2 = self.W2_init.clone().to(dtype=dtype, device=device).repeat(batch, 1, 1, 1)
            strength = torch.zeros(batch, self.sqrt_n, device=device, dtype=dtype)
            last_seen = torch.zeros(batch, self.sqrt_n, device=device, dtype=dtype)
            current_time = 0
        else:
            w1, w2 = state['W']
            strength = state['strength']
            last_seen = state['last_seen']
            current_time = state['time']

        # Project input to state space
        K = self.k_proj(x)  # (batch, seq_len, d_state)
        V = self.v_proj(x)  # (batch, seq_len, d_state)
        gate = torch.sigmoid(self.selection_gate(x))  # (batch, seq_len, 1)

        outputs = []
        error_signals = []

        # Process each token sequentially (recurrent, no unrolling)
        for t in range(seq_len):
            current_time += 1

            # Reshape for block-diagonal structure
            kt = K[:, t, :].view(batch, self.sqrt_n, self.sqrt_n)
            vt = V[:, t, :].view(batch, self.sqrt_n, self.sqrt_n)
            gt = gate[:, t, :]  # (batch, 1)

            # --- TTT Forward Pass (Block-Diagonal Matrices) ---
            k_in = kt.unsqueeze(-2)  # (batch, sqrt_n, 1, sqrt_n)
            hidden = torch.matmul(k_in, w1).squeeze(-2)  # (batch, sqrt_n, sqrt_n)

            # Butterfly-like permutation (transpose for routing)
            hidden_routed = hidden.transpose(-1, -2)  # (batch, sqrt_n, sqrt_n)

            h_routed_in = hidden_routed.unsqueeze(-2)  # (batch, sqrt_n, 1, sqrt_n)
            vt_pred = torch.matmul(h_routed_in, w2).squeeze(-2)  # (batch, sqrt_n, sqrt_n)

            # Prediction error
            error = vt_pred - vt  # (batch, sqrt_n, sqrt_n)

            # --- Time-Aware Decay Component (Ebbinghaus) ---
            activity = kt.norm(dim=-1)  # (batch, sqrt_n) - which blocks are active?
            delta_t = (current_time - last_seen).float()  # Time since last access

            # Time gate: log-based approximation to power-law decay
            time_gate = 1.0 / torch.clamp(torch.log1p(delta_t / 10.0), min=1.0)

            # Combined decay: time modulates strength
            decay_strength = strength * time_gate  # (batch, sqrt_n)
            decay_rate = self.base_decay / (1.0 + decay_strength)  # (batch, sqrt_n)

            # --- TTT Learning (Gradient-Based Weight Updates) ---
            h_routed_col = hidden_routed.unsqueeze(-1)  # (batch, sqrt_n, sqrt_n, 1)
            err_row = error.unsqueeze(-2)  # (batch, sqrt_n, 1, sqrt_n)
            grad2 = torch.matmul(h_routed_col, err_row)  # (batch, sqrt_n, sqrt_n, sqrt_n)

            # Backprop error through w2 to get gradient for w1
            grad_h_routed = torch.matmul(err_row, w2.transpose(-1, -2))
            grad_h = grad_h_routed.squeeze(-2)  # (batch, sqrt_n, sqrt_n)

            k_col = kt.unsqueeze(-1)  # (batch, sqrt_n, sqrt_n, 1)
            grad_h_row = grad_h.unsqueeze(-2)  # (batch, sqrt_n, 1, sqrt_n)
            grad1 = torch.matmul(k_col, grad_h_row)  # (batch, sqrt_n, sqrt_n, sqrt_n)

            # Weight updates with selection gating
            step = self.lr * gt.view(batch, 1, 1, 1)
            w1 = w1 - step * grad1
            w2 = w2 - step * grad2

            # --- Consolidation & Ebbinghaus Decay ---
            recon_quality = 1.0 / (1.0 + error.norm(dim=(1, 2), keepdim=True).squeeze(-1))

            # Update strength: reinforce successful predictions.
            # v6.1 FIX: cap at max_spacing_boost. Previously unbounded, which
            # drove decay_rate -> 0 over long sessions and silently disabled
            # decay toward the axiom anchors.
            spacing_factor = torch.log1p(delta_t) * activity
            strength = torch.clamp(
                strength + (recon_quality * spacing_factor * gt.squeeze(-1) * 0.05),
                max=self.max_spacing_boost
            )

            # Update recency: mark which blocks were active
            last_seen = torch.where(
                activity > 0.1,
                torch.full_like(last_seen, float(current_time)),
                last_seen
            )

            # Decay weights toward axiom anchors (W_init)
            decay_factor = decay_rate.view(batch, self.sqrt_n, 1, 1)
            w1_init = self.W1_init.to(dtype=dtype, device=device)
            w2_init = self.W2_init.to(dtype=dtype, device=device)

            w1 = w1 * (1 - decay_factor) + w1_init * decay_factor
            w2 = w2 * (1 - decay_factor) + w2_init * decay_factor

            # --- Output ---
            yt = vt_pred.transpose(-1, -2).reshape(batch, self.d_state)
            outputs.append(yt)
            error_signals.append(error.norm(dim=(1, 2), keepdim=True).squeeze(-1))

        # Stack, project back to embedding space
        output = torch.stack(outputs, dim=1)  # (batch, seq_len, d_state)
        output = self.out_proj(output)  # (batch, seq_len, d_model)

        error_signal = torch.stack(error_signals, dim=1)  # (batch, seq_len, 1)

        new_state = {
            'W': (w1, w2),
            'strength': strength,
            'last_seen': last_seen,
            'time': current_time
        }

        return output, error_signal, new_state


# ============================================================================
# COMPONENT 3: EPISTEMIC ROUTER
# ============================================================================

class EpistemicRouter(nn.Module):
    """
    Routes MTR output through the 6 epistemic layers (LAYER_NAMES).
    Each layer has its own semantic projection and salience gate, so
    target_layer selection yields genuinely distinct representations.

    Saliences are INDEPENDENT sigmoids (each layer free in [0, 1], no
    sum-to-one constraint). Downstream calibration depends on this regime:
    mtr_grain_bridge extracts concepts at salience > 0.3, and
    DissonanceSensor's delta_threshold assumes sigmoid-scale gaps.

    Kappa controls gate sharpness (rigidity vs fluidity) and is supplied
    per-query by the hat system via HatKappaMapper. Do not remove.
    """

    def __init__(self, d_model: int):
        super().__init__()
        self.d_model = d_model
        # MTR output + CoPENt signal concatenated
        self.d_routed = d_model * 2

        self.layers = list(LAYER_NAMES)

        # Semantic projection: combined context -> epistemic representation
        self.projections = nn.ModuleDict({
            layer: nn.Linear(self.d_routed, d_model)
            for layer in self.layers
        })

        # Salience gates: how relevant is this layer?
        self.salience_gates = nn.ModuleDict({
            layer: nn.Linear(self.d_routed, 1)
            for layer in self.layers
        })

    def forward(self, mtr_x: torch.Tensor, copent_x: torch.Tensor, kappa: float = 1.0) -> Dict:
        """
        Args:
            mtr_x: (batch, seq_len, d_model) - MTR semantic output
            copent_x: (batch, seq_len, d_model) - CoPENt structural signal
            kappa: float - coupling constant (rigidity, from hat system)

        Returns:
            Dict[layer_name] -> (representation, salience)
        """
        # Concatenate semantic and structural signals
        combined_context = torch.cat([mtr_x, copent_x], dim=-1)  # (batch, seq_len, d_model*2)

        epistemic_outputs = {}

        for layer_name in self.layers:
            # Project to epistemic layer representation
            representation = torch.relu(self.projections[layer_name](combined_context))

            # Compute salience with kappa scaling
            raw_salience = self.salience_gates[layer_name](combined_context)
            salience = torch.sigmoid(raw_salience * kappa)

            epistemic_outputs[layer_name] = (representation, salience)

        return epistemic_outputs


# ============================================================================
# COMPONENT 4: DISSONANCE SENSOR (Pain Receptor)
# ============================================================================

class DissonanceSensor(nn.Module):
    """
    Detects structural dissonance when epistemic layers contradict each other.

    Two types of dissonance:
    1. High TTT error: Model can't predict next token
    2. High layer divergence: Layer saliences are too different

    Divergence pairs (spec-canonical names):
      - L0_ground_truth vs L2_heuristic: facts vs working theory
      - L2_heuristic vs L4_hat: working theory vs behavioral mode

    Thresholds are calibrated for the independent-sigmoid salience regime
    of EpistemicRouter. If the routing regime ever changes (e.g. softmax),
    these must be recalibrated.
    """

    def __init__(self, mtr_threshold: float = 0.3, delta_threshold: float = 0.4):
        super().__init__()
        self.mtr_threshold = mtr_threshold
        self.delta_threshold = delta_threshold

    def forward(self, error_signal: torch.Tensor, snapshot: Dict) -> Dict:
        """
        Args:
            error_signal: (batch, seq_len, 1) - TTT prediction error
            snapshot: Dict[layer_name] -> (representation, salience)

        Returns:
            Dict with dissonance flags and diagnostics
        """
        # Type 1: High TTT error = confusion
        high_error = error_signal > self.mtr_threshold

        # Extract salience from epistemic layers
        _, l0_sal = snapshot['L0_ground_truth']
        _, l2_sal = snapshot['L2_heuristic']
        _, l4_sal = snapshot['L4_hat']

        # Type 2: Layer divergence = incoherence
        delta_L0_L2 = torch.abs(l0_sal - l2_sal)  # Facts vs working theory
        delta_L2_L4 = torch.abs(l2_sal - l4_sal)  # Working theory vs hat

        structural_interrupt = (delta_L0_L2 > self.delta_threshold) | \
                               (delta_L2_L4 > self.delta_threshold)

        return {
            'dissonance_active': high_error | structural_interrupt,
            'delta_L0_L2': delta_L0_L2,
            'delta_L2_L4': delta_L2_L4,
        }


# ============================================================================
# COMPONENT 5: COMPLETE HYBRID MODEL
# ============================================================================

class KitbashMTREngine(nn.Module):
    """
    Complete MTR-Ebbinghaus system: CoPENt + MTR + Epistemic Router + Dissonance Sensor.

    This is the neural core. Orchestration (routing to grains/cartridges/LLM)
    happens above.

    v6.1: kappa is a first-class parameter again — it is the hat system's
    control channel into routing rigidity (HatKappaMapper.get_kappa(hat)).
    """

    def __init__(self, vocab_size: int = 50257, d_model: int = 256, d_state: int = 128, dream_bucket_writer=None):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.d_state = d_state
        self.dream_bucket_writer = dream_bucket_writer

        # Token embedding (no positional embedding — CoPENt handles position)
        self.embed = nn.Embedding(vocab_size, d_model)

        # Core components
        self.copent = SparseContextualCounter(d_model)
        self.mtr = MTREbbinghausLayer(d_model, d_state)
        self.epistemic_router = EpistemicRouter(d_model)
        self.dissonance_sensor = DissonanceSensor()

        # Output head (for generation, but typically used via epistemic layers)
        self.lm_head = nn.Linear(d_model, vocab_size)

    def forward(
        self,
        token_ids: torch.Tensor,
        state: Optional[dict] = None,
        target_layer: str = DEFAULT_TARGET_LAYER,
        kappa: float = 1.0
    ) -> Tuple[torch.Tensor, torch.Tensor, dict]:
        """
        Args:
            token_ids: (batch, seq_len) - token indices
            state: Optional dict with keys: W, strength, last_seen, time, copent_pos
            target_layer: Which epistemic layer to extract output from (see LAYER_NAMES)
            kappa: Coupling constant (rigidity, >1=rigid, <1=fluid; hat-driven)

        Returns:
            logits: (batch, seq_len, vocab_size)
            error_signal: (batch, seq_len, 1)
            new_state: Updated state dict
        """
        if target_layer not in LAYER_NAMES:
            raise ValueError(
                f"Unknown target_layer '{target_layer}'. "
                f"Valid (spec-canonical) names: {LAYER_NAMES}"
            )

        batch, seq_len = token_ids.shape

        # Embed tokens (no fixed positional encoding)
        x = self.embed(token_ids)  # (batch, seq_len, d_model)

        # Validate state format if provided
        if state is not None and 'W' not in state:
            # State exists but missing MTR weights (malformed), reinitialize
            state = None

        # CoPENt: generate structural positional signal
        last_copent = state['copent_pos'] if state and 'copent_pos' in state else None
        copent_signal, new_copent = self.copent(x, last_copent)  # (batch, seq_len, d_model)

        # MTR: temporal reasoning with learning
        mtr_output, error_signal, new_mtr_state = self.mtr(x, state)

        # Merge CoPENt position into state for next call
        new_mtr_state['copent_pos'] = new_copent

        # Epistemic routing: project through all 6 layers
        epistemic_outputs = self.epistemic_router(mtr_output, copent_signal, kappa)

        # Extract target layer and generate output
        representation, salience = epistemic_outputs[target_layer]
        logits = self.lm_head(representation)

        return logits, error_signal, new_mtr_state

    def get_epistemic_snapshot(
        self,
        token_ids: torch.Tensor,
        state: Optional[dict] = None,
        kappa: float = 1.0
    ) -> Dict:
        """
        Get full epistemic snapshot without generating logits.
        Used for diagnostics, sleep cycles, dissonance detection.
        """
        x = self.embed(token_ids)

        last_copent = state['copent_pos'] if state and 'copent_pos' in state else None
        copent_signal, _ = self.copent(x, last_copent)

        mtr_output, _, _ = self.mtr(x, state)

        return self.epistemic_router(mtr_output, copent_signal, kappa)

    def log_consistency_violation(self, returned_fact_id: int,
                                  returned_confidence: float,
                                  error_signal: float,
                                  mtr_state_time: int = 0,
                                  context: Optional[Dict[str, any]] = None,
                                  session_id: Optional[str] = None) -> None:
        """
        Log consistency violation to dream bucket.

        When search returns high-confidence result but MTR error_signal is high,
        that's a dissonance worth investigating.
        """
        if self.dream_bucket_writer is None:
            return

        # Log only if there's significant dissonance
        if error_signal > 0.5 and returned_confidence > 0.8:
            from dream_bucket import log_consistency_violation
            log_consistency_violation(
                self.dream_bucket_writer,
                source_layer="mtr",
                returned_fact_id=returned_fact_id,
                returned_confidence=returned_confidence,
                mtr_error_signal=error_signal,
                mtr_state_time=mtr_state_time,
                dissonance_type="high_confidence_low_coherence",
                context=context,
                session_id=session_id
            )


# ============================================================================
# SMOKE TEST (full contract suite lives in TEST-MTR_v6_1_contract.py)
# ============================================================================

if __name__ == "__main__":
    print("=== Kitbash MTR-Ebbinghaus Engine v6.1 (smoke test) ===\n")

    torch.manual_seed(42)

    engine = KitbashMTREngine(vocab_size=1000, d_model=256, d_state=144)  # 144 = 12^2
    sensor = DissonanceSensor()

    token_ids = torch.randint(0, 1000, (1, 20))
    logits, error, state = engine(token_ids, kappa=1.0)
    print(f"forward:    logits {tuple(logits.shape)}, error mean {error.mean():.4f}, time {state['time']}")

    snapshot = engine.get_epistemic_snapshot(token_ids, state, kappa=2.0)
    assert set(snapshot.keys()) == set(LAYER_NAMES), "snapshot keys must match LAYER_NAMES"
    dissonance = sensor(error, snapshot)  # must not KeyError (v6 regression)
    print(f"dissonance: active on {dissonance['dissonance_active'].sum().item()} tokens")

    print("\nSmoke test passed. Run TEST-MTR_v6_1_contract.py for the full suite.")
