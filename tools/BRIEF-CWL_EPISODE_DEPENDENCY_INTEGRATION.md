# Brief: Context Window Lifecycle (CWL) — Episode Dependency Tracking for Kitbash

**Status:** Design phase (high-signal architecture discussion)  
**Target:** Post-1.0 sleep pipeline enhancement; prototype logging during current holding phase  
**Audience:** Architecture decisions; Stage 5 recalibration planning

---

## Executive Summary

pi-cwl's **Context Window Lifecycle** introduces a structured context-eviction model: agents annotate work as typed, dependency-linked *episodes* (exploratory vs. action), then a deterministic policy evicts old, completed content while preserving active reasoning context. 

Kitbash already has the building blocks in place—**Dream Bucket logs traces**, **procedural edges** capture topology, **grain tiering** distinguishes hot/cold content. CWL's contribution is making episode boundaries and dependencies *explicit during operation*, enabling Stage 5 recalibration (and post-1.0 sleep Tier 2) to make better cache-eviction and hypothesis-prioritization decisions.

**Key insight:** The dependency graph (which exploratory work informed which actions) is available in your trace chains *today*. Formalizing this doesn't require new infrastructure—just richer annotation of what you're already logging.

---

## Why This Matters for Kitbash

### Current State
- You log **traces** (fact→fact chains) to Dream Bucket during queries.
- You extract **procedural edges** (co-occurrence topology) from traces in sleep Stage 1.5.
- You tier grains by access recency + inference cost; **MTR ranks by salience**.
- You *know* which cartridges informed which decisions, but this knowledge lives in trace chains and isn't queryable as a graph of "episode dependencies."

### CWL's Structural Insight
Treat every query session as a sequence of typed work units:
- **Exploratory episodes** (`expl`): Grain activations, cartridge reads, fact retrievals. No side effects in the environment. Output: learned topology/context.
- **Action episodes** (`act`): Decisions that produce durable effects (hypothesis generation, cartridge crystallization, Dream Bucket indexing). Effects are already persisted.

When context (ops log, active traces) gets too large:
- Drop action episodes first; their effects are done, side effects are persisted.
- Keep exploratory context that *active* decisions are reasoning over.
- Respect dependencies: if action A depends on exploration B, keep B until A is dropped.

### Why Kitbash Needs This

1. **Stage 5 recalibration doesn't know what to preserve.** Right now you're gated on "real usage data." The data tells you *what happened* but not *which decisions were necessary*. If you log episode boundaries + dependencies, you can analyze: "Would dropping this exploratory trace have changed the outcome of this action?"

2. **Post-1.0 sleep Tier 2 can be smarter about hypothesis generation.** Tier 1 (waking consolidation) runs every session. Tier 2 (subconscious hypotheses, post-1.0) should ask: "What exploratory patterns predict successful action phases?" Episode dependencies give you the causal signal.

3. **Grain eviction can respect topology.** You're already doing this implicitly (MTR + hot/cold tiering). Formalizing dependencies means you can evict isolated grains aggressively while keeping high-fan-out grains even if cold.

4. **The tool registry can declare work type.** Instead of inferring whether a tool is exploratory or action-y, each tool can self-declare. This is zero runtime cost and enriches every trace automatically.

---

## Design: Three Parts

### Part 1: Tool Metadata — Self-Declaration of Work Type

Add an optional `work_type` field to each tool's schema:

```python
# In tool registry or SPEC files:
class ToolSchema:
    name: str                # e.g., "document_preprocessor"
    work_type: str           # "exploratory" | "action" | "neutral"
    depends_on_results: bool # Does this tool need prior exploratory outputs?
```

**Examples:**
- Document preprocessor → `exploratory` (outputs descriptions, topology)
- Text search → `exploratory` (information gathering)
- Cartridge crystallizer → `action` (persists grains to cartridge)
- MTR ranker → `neutral` (pure compute, no side effects)

**Cost:** ~10 lines per tool; optional field with safe default.

### Part 2: Episode Annotation Layer

Lightweight agent annotation during normal operation. Add a single tool to the tool registry:

```
annotate_episode_boundary(phase: "expl" | "act", summary: str) -> {"episode_id": str}
```

The agent calls this when transitioning between exploratory work (reading documents, activating grains, building context) and action work (making decisions, triggering consolidation, writing to Dream Bucket).

**Example query flow:**
```
1. User: "What's the relationship between thermodynamics and entropy?"
2. Agent starts exploratory phase → annotate_episode_boundary("expl", "reading thermodynamics cartridge")
3. Agent calls: grain_activation(thermodynamics_grain_id)
4. Agent calls: text_search("entropy definitions")
5. Agent transitions → annotate_episode_boundary("act", "generate hypothesis linking 2nd law to information theory")
6. Agent calls: log_hypothesis(...)
```

**Cost:** One lightweight tool (30 lines), minimal agent overhead.

### Part 3: Automatic Dependency Graph Construction

Dream Bucket + sleep procedural_edge_extractor already log traces. Add a new step in sleep pipeline (Stage 1.5b, post-edge extraction):

```python
class EpisodeGraphBuilder:
    """
    Runs after procedural_edge_extractor (Stage 1.5).
    Reconstructs episode boundaries from:
      1. Explicit annotations (episode_boundary tool calls)
      2. Inferred from tool work_type declarations
    Builds dependency graph:
      - Which tools/grains each episode touched
      - Which episodes each action depends on
      - Salience of exploratory context (fan-out)
    Outputs to indices/episode_dependency_graph.json
    """
    
    def build_graph(self) -> Dict[str, Any]:
        episodes = self._reconstruct_episodes()
        dependencies = self._infer_dependencies(episodes)
        graph = {
            "episodes": episodes,           # episode_id -> {phase, summary, tools, grains}
            "dependencies": dependencies,   # action_id -> [expl_id, expl_id, ...]
            "dependency_matrix": ...,       # For eviction policy queries
            "salience": ...,                # Which expl episodes have high fan-out
        }
        return graph
```

**Cost:** ~150 lines; runs once per sleep cycle; deterministic replay from logs.

---

## Prototype Plan (This Holding Phase)

### Goal
Collect episode metadata during the two-week data window. See if the dependency graph structure makes sense before committing to eviction policy.

### Minimal Implementation
1. **Add tool metadata** (5 min): Annotate existing SPEC files with `work_type`. No code change yet.
2. **Add annotation tool** (30 min): Implement `annotate_episode_boundary` in kitbash_registry.py. Log to Dream Bucket as a new event type: `"event_type": "episode_boundary"`.
3. **Parse during sleep Stage 1.5b** (60 min): After procedural edges are extracted, read all `episode_boundary` events + traces, reconstruct episodes, write to `episode_dependency_graph.json`.

### What You'll Measure
- **Annotation overhead:** Does calling `annotate_episode_boundary` add measurable latency per query?
- **Graph coherence:** Do dependency graphs form DAGs or cycles? Are action episodes actually independent?
- **Salience signal:** Do high-fan-out grains (discovered via graph analysis) match your intuition about what *should* be preserved?

### Risk: If It's Noise
- Delete `episode_dependency_graph.json` from indices.
- Keep Dream Bucket logs (non-destructive archival).
- Lesson learned for post-1.0 design without implementation sunk cost.

---

## Post-1.0 Eviction Policy (Sketch)

Once you have real dependency graphs, implement CWL-style eviction:

```python
class EpisodeEvictionPolicy:
    """
    Graduated eviction when token budget exceeded.
    Level 0: Remove reasoning traces (Dream Bucket observations, hypotheses)
    Level 1: Remove bulk exploratory outputs (cartridge reads, facts)
    Level 2: Remove intermediate artifacts (hypothesis candidates, pattern matches)
    Level 3: Remove whole exploratory episodes (oldest, lowest fan-out)
    Level 4: Remove action episodes (oldest, effects already persisted)
    
    Invariant: Never drop exploratory episode while action depends on it.
    """
    
    def evict_to_budget(self, ops_log, episode_graph, target_tokens):
        # Walk graph in priority order
        candidates = self._collect_candidates(episode_graph)
        while get_token_count(ops_log) > target_tokens:
            to_drop = candidates.pop(0)
            ops_log = self._drop(to_drop)
```

**Ties to sleep pipeline:** This runs in Stage 5 recalibration OR post-1.0 sleep Tier 2 hypothesis generation (deciding what exploratory context to carry forward).

---

## Integration Points

### Dream Bucket
- New log type: `"episodes"` (metadata) and `"episode_boundaries"` (markers).
- Optional enrichment of existing `"traces"` with `episode_id` field.
- No structural changes; additive only.

### Sleep Procedural Edge Extractor (Stage 1.5)
- After current edge extraction, run EpisodeGraphBuilder.
- Inputs: traces.jsonl, episode_boundary events.
- Output: episode_dependency_graph.json (new index).

### Tool Registry
- Tool schema gains optional `work_type` field.
- One new tool: `annotate_episode_boundary`.
- No changes to tool execution model.

### MTR / Grain Activation
- No changes needed. But: When querying for grain salience, can now cross-reference episode_dependency_graph to ask "how many decision phases depend on this grain?"

---

## Decision Points

**Q1: Do you want to prototype logging now (holding phase) or wait until post-1.0?**

*Our take:* Logging is free (append-only, non-blocking). Learning what the dependency graph looks like during real usage is high-value signal for Stage 5 decisions. Recommend prototyping now.

**Q2: Should episode annotation be mandatory (every query) or optional (agent decides)?**

*Our take:* Optional for now. Let the agent mark transitions when it's clear. Infer the rest from tool work_type declarations. This keeps cognitive overhead low while still enriching logs.

**Q3: Is the eviction policy something you want to spec now or defer to post-1.0?**

*Our take:* Defer. The prototype will tell you if the dependency graph is actually useful. If it's noisy/cyclical/useless, you save implementation time.

---

## Deliverables

### Phase 1 (This Holding Window)
- [ ] SPEC-episode_annotation_tool_v1.md (30 lines)
- [ ] Add `work_type` metadata to existing tool SPECs (10 min per tool)
- [ ] Implement `annotate_episode_boundary` in kitbash_registry.py + Dream Bucket logging
- [ ] Implement EpisodeGraphBuilder; run in sleep Stage 1.5b
- [ ] Collect dependency graph data for two weeks

### Phase 2 (Post-1.0, Stage 5+)
- [ ] SPEC-eviction_policy_v1.md (architectural design)
- [ ] Implement EpisodeEvictionPolicy
- [ ] Integrate with sleep Tier 2 hypothesis generation

---

## Open Questions / Scavengeable Ideas

**From CWL paper but deferred:**
- How to handle agent tool-use errors within episodes? (If an exploratory call fails, do we still log it?)
- Cycle detection: If episodes form cycles in dependency graph, what's the eviction order?
- Cross-session episodes: Should long-running patterns (e.g., "recurring grain activation for X topic") be tracked as meta-episodes?

**From Kitbash-specific:** 
- Should the ternary crush system declare a work_type? (It's neither exploratory nor action, it's introspective.)
- Can episode dependencies inform LoRA training priorities in post-1.0 memory era? (Which grains are most-depended-on = highest ROI for specialization?)

---

## File Layout

After implementation, Dream Bucket structure becomes:

```
dream_bucket/
├── live/
│   ├── traces.jsonl              (existing)
│   ├── episodes.jsonl            (NEW: episode metadata)
│   ├── episode_boundaries.jsonl  (NEW: explicit transitions)
│   └── ...
├── indices/
│   ├── procedural_edge_graph.json    (existing)
│   ├── episode_dependency_graph.json (NEW)
│   └── ...
└── ...
```

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Episode annotation overhead (latency per query) | Low | Benchmark; if >5ms, make async |
| Dependency graph is cyclical (breaks DAG assumption) | Medium | Log cycles to violation bucket; redesign eviction if needed |
| Tool `work_type` metadata is wrong for some tools | Low | Tool schema has safe defaults; misclassification → low-priority episodes, safe fallback |
| Stage 1.5b graph builder is slow (blocking sleep) | Medium | Implement as Stage 1.5b.checkpoint; don't block Stage 2 if building takes >30s |

---

## Summary

**What:** Formalize episode boundaries (exploratory vs. action) and their dependencies, making existing trace chains queryable as a structured causality graph.

**Why:** Enables Stage 5 recalibration to make informed decisions about what context to preserve, and informs post-1.0 sleep pipeline cache policies.

**How:** Add lightweight tool-metadata annotations + one optional agent tool + one sleep stage processor. Collect data now; implement eviction policy post-1.0.

**Cost:** ~2 hours implementation + data collection during holding phase. Zero risk if findings are inconclusive.

**Payoff:** Better long-horizon agent behavior; reduced hallucination when operating near token budget ceiling; informed design for post-1.0 learning priorities.
