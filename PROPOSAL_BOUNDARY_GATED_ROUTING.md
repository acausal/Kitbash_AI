# Proposal: Boundary-Gated Routing & Sleep-Trained Fusion

**Status:** DESIGN ONLY — deferred. Do not implement until the prerequisites below are met.
**Date:** 2026-07-07
**Origin:** research_brief_attention_encoding_copent (2026-07-08), sections 4–6 — the recommendations as actually written, not as transplanted into MTR v6. See POSTMORTEM_MTR_v6.md for why the first attempt failed.
**Baseline:** MTR_v6_1.py (v5.5 semantics, spec-canonical layer names, sigmoid salience regime)

---

## Prerequisites (hard gates, in order)

None of this proposal is implementable until all three hold. This is the lesson of v6: these mechanisms are training-dependent, and building them without their substrate produces frozen random parameters wearing an "improvement" label.

1. **Phase 5 complete.** Mutations 1–2 and Redis bus integration done; the L1/L2 grain separation in particular matters here because Stage C's routing prior wants clean layer semantics.
2. **Evaluation harness exists and has baselined v6.1.** Every stage below ships only if the harness shows improvement on the metrics defined in §6. Without baseline numbers, this proposal is unfalsifiable and should not be started.
3. **Sleep pipeline can emit training triples.** The plumbing described in §5 — (query trace, epistemic snapshot, outcome label) records extracted during nightly consolidation. This is the "blood supply" the v6 organs lacked.

A useful mental model: this proposal is the same "microspecialist NN" pattern already planned for the ambiguity resolvers — small modules trained from Dream Bucket signal during sleep, frozen during inference. The router's learnable parameters are simply the first microspecialists.

---

## 1. What the Brief Actually Proposed

Three mechanisms, in increasing order of ambition:

**Learned fusion** (brief §4): replace additive/concatenative merging of the MTR content signal and CoPENt structural signal with a gate — `fused = g·mtr + (1−g)·copent` where `g = sigmoid(MLP([mtr; copent]))`. The empirical hierarchy across the brief's comparative studies puts learned gating above concatenation above addition, *when trained*.

**Adaptive temperature** (brief §5): routing sharpness controlled by a scheduled or learnable temperature rather than a fixed constant. Note for Kitbash: κ is not a fixed constant — it is the hat system's per-query control channel. Temperature here means a *learned residual on top of* κ, never a replacement for it.

**Boundary-gated hierarchical routing** (brief §6.2): the recommendation v6 never actually built. Level 1: CoPENt's boundary detection determines the current *structural region*. Level 2: content routing assigns epistemic layers *within* that region. The insight is that "which structural regime are we in" (new topic vs. continuation vs. confidence shift) should constrain "which epistemic layers are plausible" before content ever votes. This mirrors THOR-MoE's task-router→token-router split.

## 2. Stage A — Sleep-Trained Fusion Gate

**Design.** Resurrect `LearnedGate` (the v6 module structure was fine) with one change: **zero-initialize the final linear layer** (weight and bias), so `g = sigmoid(0) = 0.5` exactly and `fused = 0.5·(mtr + copent)` — scaled addition, the proven baseline. The module is behaviorally inert at install. Every subsequent change to its behavior comes from sleep training against real signal, so the gate can only ever have *earned* its deviation from baseline. This identity-at-init trick is the same principle as zero-init adapters in the LoRA literature and should be the house style for all future learnable modules.

**Wiring.** `fused` feeds the router input (replacing the concat path — router input dimension drops from 2·d_model to d_model, so per-layer projections shrink; this is a state-dict-breaking change for router weights, acceptable because router weights are untrained today anyway). Keep the raw `mtr` and `copent` tensors available to diagnostics.

**Training.** Nightly, frozen at inference. See §5 for signal.

**Effort:** small. Module exists in v6; the work is the zero-init, rewiring, and the training step in the sleep pipeline.

## 3. Stage B — Temperature as κ-Residual

**Design.** Effective sharpness = `κ · softplus(θ)/softplus(0)` where θ is a learned scalar initialized to 0 — i.e., exactly κ at install, hat pathway fully preserved, with the sleep pipeline free to learn a global sharpness correction if the signal supports one. The brief's alternative (scheduled annealing) maps onto Kitbash as annealing *within each nightly training run* (soft targets early in the run, hard late), not over operational time — operational time has no epochs.

**Guard.** θ gets a clamp (e.g., effective multiplier ∈ [0.25, 4.0]) so a bad training night cannot silently flatten or spike routing sharpness beyond what the hat system can compensate for.

**Effort:** trivial once Stage A's training step exists. Ship after Stage A proves the training loop works, not simultaneously.

## 4. Stage C — Boundary-Gated Hierarchical Routing

The ambitious one. Two sub-stages, and the first is mandatory before any code.

### 4.0 Validate the boundary detector first

An honest audit note: CoPENt's break-detection gate (`self.gate` linear + 0.85 threshold) is *itself untrained*. Its "boundaries" today are artifacts of random initialization. Before building anything on top of boundary detection, run the measurement experiment:

- Take a corpus of real query sessions with human-annotated (or heuristically labeled — hat changes, cartridge switches, long gaps) topic boundaries.
- Measure precision/recall of CoPENt's detected breaks against those labels, sweeping the threshold (brief open question #1).
- **Gate:** if random-init CoPENt breaks don't correlate with real structure, Stage C's Level 1 has no foundation, and the boundary detector itself becomes the first thing to sleep-train (same triple plumbing, labels from session structure).

This experiment needs only the harness and logged sessions — it can run before Stages A/B and is arguably the cheapest high-information experiment in this whole proposal.

### 4.1 The routing prior

**Region features** (cheap, derived from existing CoPENt internals): count of breaks since session start, tokens since last break, mean gate activation in current region, whether a break occurred within the last N tokens.

**Region classifier:** a small linear (or two-layer) head mapping region features → a *prior logit vector* over the 6 layers (`LAYER_NAMES` order). Semantic intent: "just after a topic break, L3_context and L0_ground_truth are more plausible; deep in a stable region, L2_heuristic dominates; hat changes spike L4_hat."

**Combination:** additive in logit space — per-layer salience becomes `sigmoid((raw_salience + prior_logit) · κ_eff)`. Zero-init the classifier head so the prior is 0 everywhere at install (identity-at-init again). **Deliberately stay in the sigmoid regime.** The v6 incident showed the downstream cost of a regime change (bridge's >0.3 gate, sensor's delta thresholds); the prior modulates the existing regime rather than replacing it. If a future version genuinely wants sum-to-one softmax routing, that is a migration project with its own checklist: recalibrate `mtr_grain_bridge` extraction threshold, recalibrate `DissonanceSensor.delta_threshold`, re-baseline the harness, and update the regime assertion in TEST-MTR_v6_1_contract.py — all four, atomically.

**Inference hardening** (brief §8 step 5): optional top-k masking of layer saliences at inference, k=2, entropy-adaptive later. Config-flagged, off by default.

**Effort:** moderate. The classifier is small; the work is the feature extraction, the training step, and the harness experiments.

## 5. Training Signal (the substrate v6 lacked)

All stages train from the same plumbing: a sleep-pipeline stage that extracts **(query trace, epistemic snapshot, outcome label)** triples from the day's operation.

**Where labels come from** — this is where the corollary discharge framing does real work:
- *Positive:* queries where the returned grain/fact was confirmed (used downstream, reinforced, no violation logged) → the snapshot's salience pattern for the layer that sourced the answer is a positive target.
- *Negative:* Dream Bucket consistency violations (`high_confidence_low_coherence` events, contradicted hypotheses) → the salience pattern that produced them is a negative target. Violations aren't noise to suppress; they are exactly the supervision that tells the router where its topology is wrong.
- *Boundary labels* (for 4.0/Level 1): hat changes, cartridge hot-swaps, and long temporal gaps as weak topic-boundary supervision.

**Objective sketch:** for each triple, a per-layer binary target vector (source layer of a confirmed answer → 1; layers implicated in violations → 0; unobserved layers masked out). BCE over unmasked layers, backpropagated into gate MLP, θ, prior head, and salience gates. Small learning rate, few epochs per night, gradient-norm clipping, and a **regression guard**: after each nightly run, replay a held-out set of the previous week's confirmed-good triples; if accuracy drops beyond tolerance, revert to the prior night's checkpoint. Checkpoints are tiny (a few thousand parameters) — keep 30 days of them in the archive tier.

**Volume reality check:** at personal-use query rates, nightly triples number in the dozens-to-hundreds. That is fine for parameters this small, but it means weeks-to-months before the gate meaningfully deviates from its identity init. Set expectations accordingly; this is a slow-compounding investment, which is consistent with the project's whole thesis.

## 6. Evaluation Gates

Metrics the harness must support before Stage A begins, each with a v6.1 baseline number recorded first:

1. **Routing usefulness proxy:** fraction of confirmed-answer queries where the answer's source layer was in the top-2 saliences.
2. **Dissonance precision:** of `dissonance_active` firings, fraction that correlate with a subsequently logged violation (true alarms vs. noise).
3. **Concept-extraction yield:** count and downstream-use rate of concepts extracted by `mtr_grain_bridge` per 100 queries (this metric would have caught the v6 salience-regime break within a day).
4. **Latency:** end-to-end query latency must stay within the current 6–10 ms envelope; every stage is a config flag with the flag-off path unchanged.
5. **Boundary quality** (Stage C only): CoPENt break precision/recall against weak labels, from experiment 4.0.

**Ship rule:** a stage merges only when metrics 1–3 improve or hold and metric 4 holds, measured on the harness, output pasted into the merge note. No exceptions, including for changes that "obviously" help.

## 7. Rollout Order & Rollback

Experiment 4.0 (boundary measurement) → Stage A → Stage B → Stage C, each gated on the previous stage's harness verdict. Every stage: config-flagged, identity-at-init, nightly-checkpoint rollback, contract suite green. If any stage fails its gate twice, stop and write up why before proceeding — a failed gate is Dream Bucket signal about the architecture, not an obstacle to route around.

## 8. Open Questions (park here, revisit at implementation time)

- Should the fusion gate be per-dimension (`g` a d_model vector) rather than scalar? Brief evidence is on scalar/low-dim gates; per-dimension multiplies parameters and overfitting risk at this data volume. Start scalar.
- Does the routing prior belong in MTR at all, or in the orchestrator's rule-based triage layer where it would be inspectable and hand-tunable first? A hand-written prior table (hat/recency → layer bias) could be a zero-training Stage C.0 that tests the *idea* before the *mechanism* — strongly consider this first, it is very Kitbash.
- Cross-domain transfer (brief open question #2): does a gate trained on one cartridge domain transfer to another, or does this eventually want per-cartridge gate deltas (which would slot naturally into the .kbc format alongside procedural edges)?
- Multi-scale boundaries (brief open question #3): defer entirely; single-scale must prove itself first.
