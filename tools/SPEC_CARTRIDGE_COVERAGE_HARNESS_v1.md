# SPEC: Cartridge Retrieval Coverage Harness v1

**Purpose:** Generate synthetic queries with intentional variation to test end-to-end cartridge retrieval, grain activation, and procedural edge topology. Produce logs suitable for analyzing operational data and fixing magic numbers in Stage 1.5.

**Scope:** Single-purpose CLI harness that generates queries, runs them through the full pipeline (CartridgeLoader → MTR → GrainRouter), and validates coverage.

**Non-goals:**
- Interactive chat UI (defer to post-1.0)
- Sleep pipeline integration (this is waking-mind only)
- Persistent state mutations (harness is read-only on cartridges; logs append only)
- Query router classification (rule-based triage still fine)

---

## Architecture

### Phase 1: Query Generation

Three generation strategies (all produce a single unified stream):

1. **Entity Extraction** (deterministic)
   - Parse all cartridge facts for nouns, entities, key terms
   - Build single-subject queries: "What is [entity]?", "Tell me about [entity]"
   - Goal: hit every fact at least once via direct lookup

2. **Template-Based** (structured variation)
   - Define 15–20 query templates with varying structure:
     - Factual: "What [subject]?"
     - Relational: "How does [subject] relate to [object]?"
     - Comparative: "What's the difference between [subject] and [object]?"
     - Procedural: "How do I [action] with [subject]?"
     - Temporal: "When was [subject]?", "What happened to [subject]?"
   - Each template randomly instantiated with 2–3 facts from cartridge
   - Goal: generate multi-subject queries that exercise co-occurrence edges

3. **Topological Validation** (post-hoc)
   - Cross-reference retrieved facts against procedural edge graph
   - Flag facts that *should* co-occur but weren't retrieved together
   - Count actual vs. expected co-occurrence activations

### Phase 2: Execution

For each generated query:

```
1. Emit query to QueryOrchestrator.process() (end-to-end)
2. Record:
   - Query text
   - Retrieval latency
   - Facts retrieved (IDs + content)
   - Grain activations (if any)
   - MTR inference result
   - Errors (if any)
3. Append structured log entry (JSONL)
4. Accumulate coverage stats (in-memory)
```

### Phase 3: Coverage Validation

After all queries run:

```
1. Facts Accessed
   - Which fact_ids were retrieved at least once
   - Which were never touched
   - Count: X/609 covered

2. Co-occurrence Topology
   - For each edge in cartridge procedural_edges:
     - Did facts ever appear together in same retrieval?
     - Log: (fact_a, fact_b) → retrieved_together: bool, count: N
   - Produce matrix or list of topology coverage

3. Grain Activation
   - Which grains fired?
   - Which grain_ids were activated together?
   - Any activations that shouldn't have happened?

4. Summary Report
   - Fact coverage %
   - Edge coverage %
   - Grain stats (total fires, co-activations)
   - Latency quantiles (p50, p95, p99)
   - Error summary
```

---

## Input & Output

### Input

- Cartridge files (JSON or SQLite, from running Kitbash instance)
- Generation config (optional):
  - `--num_entity_queries`: how many single-subject queries (default: 609+100 buffer)
  - `--num_template_queries`: how many template-based multi-subject queries (default: 300)
  - `--seed`: RNG seed for reproducibility (default: 42)

### Output

**Files created:**

1. `coverage_harness_queries.jsonl`
   - One entry per query (executed)
   - Fields: timestamp, query_text, fact_ids_retrieved, grain_ids, latency_ms, errors

2. `coverage_harness_report.json`
   - Summary statistics
   - Fact coverage array
   - Edge coverage matrix
   - Grain activation stats
   - Latency quantiles

3. `coverage_harness_topology_gaps.txt`
   - Human-readable list of untouched facts and unaccessible edges
   - For triaging coverage gaps

4. `coverage_harness_raw_traces.txt` (optional, verbose)
   - Full trace output during execution
   - Useful for post-hoc debugging

---

## Implementation Notes

### Query Generation Strategy

1. **Entity Extraction:**
   - Load all cartridges
   - Tokenize each fact content (spaCy NER, simple regex for capitalized phrases)
   - Deduplicate entities
   - For each entity E: generate query "What is {E}?" or similar

2. **Template Instantiation:**
   - Define templates as format strings with placeholders: `[SUBJECT]`, `[OBJECT]`
   - Randomly pair facts from cartridge (with replacement okay, duplicates absorbed)
   - Instantiate 300–500 queries

3. **Deduplication:**
   - De-dup final query stream (some template + entity overlap is expected)
   - Emit unique queries in deterministic order (sorted by query text)

### Execution Loop

```python
harness = CartridgeCoverageHarness(cartridges, config)
harness.generate_queries()          # Populates query stream
harness.run_all()                    # Executes each, logs results
harness.validate_coverage()          # Analyzes topology
harness.write_reports()              # Emits files
```

### Cartridge Loading

- Assume existing CartridgeLoader or CartridgeInferenceEngine works
- Harness uses QueryOrchestrator.process(query) as black box
- Logs output at orchestrator level (no internal peeking)

### Edge Validation

After execution:
- For each edge `(fact_a, fact_b)` in cartridge.procedural_edges:
  - Search harness logs for a retrieval that included both
  - Count hits
  - Flag edges with 0 hits (potential topology gap)

---

## Success Criteria

- [ ] Query generation produces 700–1000 unique queries
- [ ] All 609 facts appear in retrieved results at least once
- [ ] Procedural edge coverage >50% (ideally 70%+)
- [ ] No crashes on execution; errors logged cleanly
- [ ] JSONL log is parseable and contains all required fields
- [ ] Report JSON can be consumed by post-processing scripts
- [ ] Gaps file is human-actionable (lists missing facts and edges)

---

## Open Questions & Deferred Decisions

1. **Multi-query sessions:** Should harness group queries into synthetic "sessions" for sleep pipeline later, or keep them flat? → **DEFER to post-1.0 sleep integration**
2. **Grain activation logging:** What's the exact format MTR → Dream Bucket → grain_ids field should use? → **ASK Isaac if grain_ids are currently populated in traces**
3. **Edge weighting:** Should coverage validation weight edges by their strength, or treat all edges equally? → **Start with unweighted; re-eval if gaps cluster on low-strength edges**
4. **Query generation weighting:** Should template instantiation prefer facts with low access counts (exploit) or random facts (explore)? → **Start with random; switch to exploitation-favoring if coverage plateaus**

---

## Files to Consult

- `QueryOrchestrator` (`query_orchestrator.py`): entry point
- `CartridgeLoader` (`cartridge_loader.py`): fact lookup
- `KitbashCartridge` (`kitbash_cartridge.py`): cartridge schema + procedural edges
- `GrainRouter` (`grain_router.py`): grain activation
- `SOCKET_MAP.md`: current health state
- `STATE_OF_THE_PROJECT_2026-07-13.md`: context on Stage 1.5 and data collection

---

## Execution Checklist

Before running:
- [ ] Redis is running (bus backbone)
- [ ] Cartridges loaded into CartridgeLoader
- [ ] BitNet + llama-server online
- [ ] QueryOrchestrator fully initialized
- [ ] Output directory exists and is writable

After running:
- [ ] Inspect `coverage_harness_queries.jsonl` for parse errors
- [ ] Check report summary (fact coverage %, edge coverage %)
- [ ] Review `coverage_harness_topology_gaps.txt` for surprises
- [ ] Paste summary + signal distribution into next design session
