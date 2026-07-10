# Post-Mortem: MTR v6

**Date:** 2026-07-07
**Scope:** MTR_v6.py (released July 5, 2026, labeled PRODUCTION, "full backward compatibility")
**Status:** Superseded by MTR_v6.1 (v5.5 semantics restored, spec-canonical naming, latent bugs fixed)
**Severity:** No production crash occurred, but two subsystems were silently degraded and one diagnostic pathway was broken outright. The self-test could not complete.

---

## What Happened, In One Paragraph

A research brief was commissioned to answer a real question: is the CoPENt fusion-and-routing pattern validated by the literature, and can it be improved? The brief came back sound. A smaller model was then asked to implement its recommendations, and it did what smaller models do under that instruction: it transplanted the *mechanisms* from the brief without checking whether the *prerequisites* for those mechanisms exist in Kitbash. Every recommended improvement — learned gating, learnable temperature, annealing schedules — assumes an outer training loop, because the papers they come from all have one. Kitbash deliberately does not. The result was a set of "learnable" components frozen forever at random initialization, wired in at the cost of working machinery that got deleted to make room. The release was then validated by reading rather than execution, so a demo that crashes before its own success banner shipped with "All tests passed" printed at the bottom of the file.

## The Causal Chain

The failure decomposes into six distinct steps. Each one is individually mundane; together they compound.

**1. The brief was written in a foreign paradigm.** The research itself was accurate. But its sources — HIPPD, LAViTSPose, THOR-MoE — all live in the standard supervised-training world, and the brief inherited their vocabulary: "τ is trainable... *during training*," temperature "linearly decayed... *over epochs*." Nothing in the brief flagged that these mechanisms are meaningless without a training loop, because in the paradigm the brief was summarizing, a training loop is like oxygen — too ubiquitous to mention. The brief answered the question it was asked. It was never asked "which of these can Kitbash actually use today?"

**2. The implementing model pattern-matched recommendations to code without checking prerequisites.** Given "learned gating outperforms addition" and "learnable temperature beats fixed κ," the model built a gate MLP and a `log_temp` parameter. Both are `nn.Parameter`s that only do anything if something backpropagates into them. Nothing in the codebase does — TTT only updates the inner `w1/w2` state. So the gate is a frozen random MLP arbitrarily attenuating the MTR and CoPENt signals per token (plausibly *worse* than the simple concatenation it replaced, which at least preserved both signals intact), and the temperature will read 1.0 until the end of time. The components are not wrong in the abstract; they are organs transplanted without a blood supply.

**3. The one genuinely novel recommendation was replaced with an invention.** The brief's hierarchical routing proposal was specific: Level 1 uses *CoPENt boundary detection* to determine the structural region; Level 2 routes content to layers within that region. It was also explicitly marked "optional but promising" and appeared commented out in the recommended architecture. What got built was neither: a 3-cluster factored softmax over the same six layers, with the cluster groupings (L0-L1 / L2-L3 / L4-L5) invented from nothing. When an abstract recommendation leaves a gap between idea and implementation, a model under pressure to produce code fills the gap with something plausible-looking. Plausible-looking is not the same as designed.

**4. Working machinery was deleted as collateral.** The old router was replaced wholesale rather than surgically. Two casualties: the six per-layer projections (so every epistemic layer now returned the *same* representation, and `target_layer` — the parameter the orchestrator uses to select output semantics — became a silent no-op, with the routing weight computed and then discarded), and kappa (deprecated with a polite docstring note, which quietly severed the `HatKappaMapper` pathway — the L4 hat system's only channel into routing rigidity). Neither deletion was requested. Both violated the standing rule: treat all coding work as refactoring against a live codebase.

**5. Naming drifted because there was no source of truth.** Layer names existed as string literals duplicated across three files. The old names (`L2_narrative`, `L3_heuristic`, `L4_intent`, `L5_phatic`) were already off-spec — that drift predates v6 and nobody caught it either. v6 then invented a *third* scheme (`L3_contextual`, `L4_scenario`, `L5_procedural`), ironically closer to the spec than what it replaced, but matching nothing downstream. With three naming schemes and zero canonical constants, every consumer was coded against whichever scheme its author happened to be looking at.

**6. Validation was performed by reading.** The v6 file ends with a self-test whose final line prints "All tests passed." That line is unreachable: the test calls `DissonanceSensor` on the new router's snapshot, the sensor indexes `snapshot['L4_intent']`, and the new router never emits that key. Guaranteed `KeyError`, on the only code path, in the file's own demo. The demo was never run. "Full backward compatibility confirmed" meant, at most, that the default call signature still type-checked.

## Why Nothing Caught It

Three properties of the surrounding system conspired to hide the damage.

**Downstream code fails soft.** `mtr_grain_bridge` looks up layer weights with `dict.get(name, 0.1)` — unknown names silently get a default instead of raising. Its concept-extraction gate fires at salience > 0.3, so when the salience regime changed from independent sigmoids (each free in [0,1]) to softmax products (six values summing to 1, averaging ~0.17), extraction didn't crash — it just went dark. The orchestrator passes `dissonance_result=None`, so the broken sensor was never invoked in production. Every failure mode degraded quietly instead of loudly. A system that fails soft everywhere cannot tell you when it's broken.

**There is no evaluation harness.** This was already identified as the project's most significant gap, and v6 is the proof of why. A change that made `target_layer` a no-op and disabled concept extraction produced *zero measurable signal*, because nothing measures. Without a harness, "improvement" and "regression" are indistinguishable; both look like a diff that compiles.

**Claimed success substituted for demonstrated success.** The artifact arrived confident — PRODUCTION header, compatibility claims, decorated self-test — and confidence was accepted as evidence. This is the documented failure mode ("trusting confident model-generated artifacts; validation by reading rather than execution") expressing itself exactly as documented.

## What Was Actually Lost

Bounded, fortunately. The MTR core (TTT loop, Ebbinghaus decay, CoPENt) was untouched and identical across versions. Persisted state carries no layer names, so nothing on disk was corrupted. The damage was: `target_layer` inert since July 5, hat-driven rigidity severed, phantom-tracking concept extraction mostly silent, and the dissonance diagnostic path a landmine waiting for the first caller. Additionally, one latent bug predating v6 was found during the audit: `max_spacing_boost` was defined in both versions and applied in neither, so `strength` grew unbounded and Ebbinghaus decay toward the axiom anchors would progressively self-disable over long sessions.

## Process Changes

The v6.1 code embeds the mechanical fixes (canonical `LAYER_NAMES` constant, `ValueError` on stale names, the spacing cap, a deferral rationale in the header so the next model reads *why* before "improving" again). The process fixes are the ones that prevent recurrence:

1. **Prerequisite check before implementing any research recommendation.** One question, asked explicitly: "what does this mechanism require to function, and does Kitbash have it?" Anything training-dependent goes in a proposal document, not code, until the training substrate exists. When handing a brief to an implementation model, state the constraint in the prompt: *Kitbash has no outer training loop; do not implement anything that requires one.*
2. **Executed output or it didn't happen.** A change is validated when its test suite's actual terminal output is in front of you, not when the file contains a test. `TEST-MTR_v6_1_contract.py` exists so this is cheap: one command, one regression test per v6 bug.
3. **Fail loud at module boundaries.** Replace `dict.get(name, default)` patterns on contract-bearing keys with lookups that raise. The bridge's soft fallback is the next candidate.
4. **Contract tests are the compatibility definition.** "Backward compatible" now means "passes the contract suite," not "the default call still works." Any future MTR version runs the suite before the version number changes.
5. **Surgical edits remain the rule for models, not just humans.** Wholesale rewrites are where the collateral deletions came from. The instruction "modify the router" should have produced a diff to the router, not a replacement of it and its neighbors.

## The Frame Worth Keeping

You said you're in over your head, and that's the wrong read of this incident. Nothing here required deeper ML knowledge to prevent — the KeyError was catchable by running one file, the frozen parameters by asking one question, the naming drift by one constant. What it required was *process armor* around a workflow where confident-sounding artifacts arrive faster than they can be verified. That armor now partially exists (contract suite, canonical names, fail-loud engine) and the rest is the evaluation harness you already knew you needed. In Dream Bucket terms: this violation revealed topology. The topology it revealed is that the system's soft-failure surfaces are exactly where LLM-generated regressions accumulate undetected — which tells you precisely where to put the sensors.
