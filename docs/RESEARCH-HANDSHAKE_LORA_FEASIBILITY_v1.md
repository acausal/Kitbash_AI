# Research Decomposition: Handshake LoRA Feasibility
**Date:** July 15, 2026  
**Status:** Pre-specification research phase  
**Purpose:** Answer "is this actually doable?" before committing to implementation spec  
**Timeline:** 1–2 weeks of targeted research (minimal code, maximum clarity)

---

## Context

**The Vague Idea:**
Procedural edges encode learned navigation patterns. Use them to generate synthetic instruct data. Train cheap LoRAs on that data. Deploy LoRAs to improve grain retrieval / routing for new base models.

**The Uncertainty:**
- Is synthetic data from edges actually useful for training?
- How would we evaluate success without ground truth?
- Has anyone actually done this before?
- What's the minimal viable experiment?
- Does it even generalize, or just memorize your specific facts?

**The Goal of This Phase:**
Answer those questions with concrete research, not speculation.

---

## Research Question 1: What Does Edge-Derived Instruct Data Look Like?

### The Question
Procedural edges are `(source_fact_id → target_fact_id, weight, traversal_count)`. How do we turn that into instruct training data?

Current mental model:
```
Edge: 42 → 137 (weight=0.72, traversals=18)
Facts: 42 = "Photosynthesis is the process by which plants convert light to energy"
       137 = "Plants store energy in glucose"

Synthetic instruct pair:
  Input: "How do plants store energy?"
  Output: "Plants store energy in glucose" (Fact 137)
  Context: "This fact is related to photosynthesis (Fact 42) with confidence 0.72"
```

**But real questions:**
1. Do we just use the fact text as-is, or do we need to generate query variations?
2. How much context do we include (just the edge, or full neighborhood)?
3. What does the "label" actually mean? (grain ranking? relevance score? binary yes/no?)
4. How many synthetic examples can we generate from 1,200 edges?

### How to Research It

**Task:** Write a concrete prototype converter (not production code, just exploration)

```python
def edge_to_instruct_examples(edge, facts_dict, procedural_edges) -> list[dict]:
    """
    Given one edge, generate synthetic instruct examples.
    Return list of {input, output, metadata}.
    """
    source_fact = facts_dict[edge.source_fact_id]
    target_fact = facts_dict[edge.target_fact_id]
    
    # Query variation 1: Direct topic extraction
    target_topic = extract_topic(target_fact.text)  # e.g., "energy storage in plants"
    
    examples = []
    
    # Example 1: Direct query
    examples.append({
        "input": f"What about {target_topic}?",
        "output": target_fact.text,
        "metadata": {
            "source_edge": f"{edge.source_fact_id}→{edge.target_fact_id}",
            "edge_weight": edge.weight,
            "label_type": "ranked_grain",
        }
    })
    
    # Example 2: Context-enriched
    neighbor_facts = get_neighborhood(edge.source_fact_id, procedural_edges)
    context = " ".join([f.text for f in neighbor_facts[:3]])
    
    examples.append({
        "input": f"Given this context: {context}. What comes next?",
        "output": target_fact.text,
        "metadata": {...}
    })
    
    return examples
```

**Effort:** 3–4 hours to write + test on 10–20 edges

**Output:** Concrete examples (5–10 synthetic pairs) that show what the data looks like. Can eyeball it and ask: "Does this look like useful training data?"

**Go/No-Go:** If examples look coherent and diverse, move to Q2. If they look like garbage or trivial, reconsider the whole approach.

---

## Research Question 2: How Do We Evaluate Without Ground Truth?

### The Question
You train a LoRA. How do you know it helped?

Options:
1. **MRR (Mean Reciprocal Rank)** — Does the LoRA-modified ranking put correct grains higher? But you don't have labeled "correct grain" data.
2. **Proxy metric: Dream Bucket violations** — If a grain was flagged as wrong, did the LoRA rank it lower? But violations are noisy.
3. **Proxy metric: Success traces** — Once success signals exist, do queries that succeeded have their top grains ranked higher by the LoRA? Circular (LoRA trained on data that produced successes).
4. **Latency/efficiency** — Does the LoRA reduce tokens needed, or speedup inference? But that's measuring something different.
5. **A/B test on real queries** — Run baseline MTR vs. LoRA-MTR on new queries, see which produces better responses. But requires running both in parallel, and "better response" is subjective.

### How to Research It

**Task:** Design the evaluation protocol, then test it on a small pilot

**Step 1: Sketch evaluation options (1 hour)**
- For each option above, write down: what data do you need? how noisy is it? can you measure it before full training?
- Which is most feasible given Kitbash's current state?

**Step 2: Implement a small pilot (4–6 hours)**
- Generate 100 synthetic examples from edges
- Train a tiny LoRA on a small model (Mistral 7B or similar, not your large model)
- Run on 50 new queries you haven't trained on
- Compare baseline MTR ranking vs. LoRA ranking on those 50 queries
- Manually inspect: did LoRA change the ranking? Was it better/worse?

**Step 3: Decide**
- If LoRA changed rankings in sensible ways → signal exists, move forward
- If LoRA didn't change anything → either data is weak or model is too small
- If LoRA changed things but in random directions → data or approach is broken

**Effort:** 1–2 hours design, 4–6 hours pilot, 2 hours analysis = 7–10 hours

**Output:** One of three conclusions:
- "Promising—LoRA learned something"
- "Unclear—need more data or different approach"
- "Dead end—abandons this line"

**Go/No-Go:** Promising → proceed to Q3. Otherwise → parking lot this idea or redesign.

---

## Research Question 3: Has Anyone Done This Before?

### The Question
"Adapter tuning on graph-derived synthetic data" — is this a known technique, or are we pioneering?

**Why it matters:** If there's prior art, we can steal their evaluation metrics + training tricks. If it's novel, we're guessing.

### How to Research It

**Task:** 3–4 hour literature search (don't go deep, just pattern-match)

**Keywords to search:**
- "LoRA graph neural networks"
- "knowledge graph adapter tuning"
- "synthetic instruct data LLM"
- "procedural edge learned routing"
- "graph-informed fine-tuning"

**Places to look:**
- arXiv (recent 6 months)
- Papers with Code
- GitHub (look for repos on "graph + LoRA" or "edge + instruct")
- Hugging Face (any models trained on graph-derived data?)

**What you're looking for:**
- Someone did X similar thing. What did they do?
- What metrics did they use to evaluate?
- Did it work? Why/why not?
- What did they warn about?

**Effort:** 2–3 hours of skimming

**Output:** 
- "Found 2–3 similar papers, here's what they did"
- Or "This is novel, but related work on X is similar"
- Or "Nothing close; we're kind of making this up"

**Go/No-Go:** Doesn't really affect yes/no (novelty isn't bad), but shapes confidence in approach. "People tried similar things with these tricks" → confidence up. "Completely novel and nobody else attempted it" → confidence down.

---

## Research Question 4: What's the Minimal Viable Experiment?

### The Question
Before committing to "train LoRA on all 1,200 edges," what's the smallest experiment that would convince you?

Current thinking: 100 synthetic examples, tiny model, 50 test queries.

**But:**
- Is that enough data? How do you know?
- Which base model? (Affects what "learned" looks like)
- How do you know 50 queries is statistically meaningful?
- What's the success criterion? (e.g., "LoRA changes top-5 ranking 30% of the time"?)

### How to Research It

**Task:** Design the minimal experiment with concrete numbers

**Sketch:**
```
Minimal experiment:
  - Data: 100 synthetic examples (from 50 edges)
  - Model: Mistral 7B (small, fast to train, widely available)
  - LoRA config: rank=8, alpha=16 (tiny, shouldn't overfit)
  - Training: 2 epochs on 100 examples (should take <10 min GPU time)
  - Test set: 30 held-out queries (new queries, not in training)
  - Evaluation: 
    - Metric 1: Does LoRA change ranking? (% of queries where top-5 differs)
    - Metric 2: Manual inspection: are changes sensible?
    - Metric 3: Latency impact? (did LoRA slow down inference?)
  - Success criterion: "Changes are sensible 70%+ of the time"
  - Effort: ~4 hours (download model, generate data, train, eval)
```

**Effort:** 1 hour to design, 4 hours to run, 1 hour to analyze = 6 hours

**Output:** Concrete experiment spec + results. Either "looks promising" or "doesn't work, here's why."

**Go/No-Go:** Results inform whether full experiment (1,200 examples, full model, larger test set) is worth trying.

---

## Research Question 5: Does It Actually Generalize?

### The Question
Say the minimal experiment works. Does that mean:
- The LoRA learned general principles about your fact topology?
- Or did it just memorize the 50 training examples?

If it's the latter, it won't help on new queries.

### How to Research It

**Task:** Generalization test (part of minimal experiment above)

**Design:**
- Train on 100 examples derived from edges in Cartridge A (e.g., general_knowledge)
- Test on 30 queries from Cartridge B (e.g., biology)
- Compare: baseline MTR vs. LoRA on cross-cartridge queries
- Hypothesis: If LoRA learned general principles, it should help even on unseen cartridge

**Alternative test:**
- Train on edges from Queries 1–1000
- Test on edges from Queries 1001–1030
- Does LoRA help on totally new queries?

**Effort:** Included in minimal experiment (no extra cost)

**Output:** "LoRA generalizes" or "LoRA only works on training distribution"

**Go/No-Go:** If generalization is weak, the whole idea doesn't scale.

---

## Contingency: What If X Fails?

### If Question 1 (data quality) Looks Bad
**Signal:** Synthetic examples are incoherent, trivial, or don't match edges

**Contingency:**
- Option A: Different converter (e.g., use edge neighborhood context, not just edge itself)
- Option B: Different training data source (e.g., success traces once they exist, instead of edges)
- Option C: Abandon LoRA, try different learning approach

**Decision trigger:** If Q1 pilot produces clearly bad examples, don't proceed to Q2. Redesign or defer.

### If Question 2 (evaluation) Can't Be Solved
**Signal:** No clear way to know if LoRA helped without ground truth

**Contingency:**
- Option A: Wait for success traces, use them as weak labels
- Option B: Invest in hand-labeling a small test set (~50 query-grain pairs)
- Option C: Accept that evaluation is subjective (manual inspection only)

**Decision trigger:** If Q2 pilot can't establish any evaluation signal, reconsider ROI.

### If Question 3 (prior art) Reveals It Doesn't Work
**Signal:** Similar attempts in literature all failed or warned against it

**Contingency:**
- Learn from their mistakes + constraints
- Adjust approach based on known failure modes
- Or accept that this might not be feasible

**Decision trigger:** Not a blocker, but shapes risk assessment.

### If Question 4 (minimal experiment) Shows No Effect
**Signal:** LoRA trained on 100 examples doesn't change ranking

**Contingency:**
- Option A: Try more data (1,000 examples instead of 100)
- Option B: Try different LoRA hyperparameters (larger rank, different alpha)
- Option C: Accept that edges aren't strong enough signal for this

**Decision trigger:** Dead end unless minimal experiment is just too small. Try 10x more data before giving up.

### If Question 5 (generalization) Fails
**Signal:** LoRA only works on training distribution

**Contingency:**
- Option A: Redesign as "domain-specific adapters" (different LoRA per cartridge)
- Option B: Different architecture (e.g., learned routing classifier, not LoRA)
- Option C: Abandon adapters, stick with static MTR + success-based heuristics

**Decision trigger:** If generalization fails, the appeal of "one LoRA fits all" is gone. Reconsider whether multi-adapter approach is worth it.

---

## Research Timeline & Checkpoints

| Week | Task | Effort | Checkpoint |
|------|------|--------|------------|
| **Week 1** | Q1: Edge-to-instruct converter + concrete examples | 3–4h | Do examples look coherent? |
| **Week 1** | Q3: Literature search | 2–3h | Any prior art? What did they do? |
| **Week 2** | Q2 + Q4 + Q5: Minimal experiment (design + run + eval) | 6–8h | Does LoRA learn anything? Generalize? |
| **Week 2** | Decision gate: Go/no-go? | 1h | Decide next phase |

**Total research effort:** 12–18 hours over 2 weeks

**Parallel:** Can happen during data collection window (doesn't block other work)

---

## Go/No-Go Decision Criteria

### Green Light: Proceed to Full Spec + Implementation
- **Q1:** Synthetic examples look coherent and diverse
- **Q2:** At least one evaluation metric is measurable and shows signal
- **Q3:** Prior art exists or doesn't contradict the approach
- **Q4:** Minimal experiment shows LoRA learns something meaningful (30%+ rank changes, sensible direction)
- **Q5:** Generalization is decent (70%+ effectiveness on held-out cartridge/queries)

### Yellow Light: Proceed with Caution / Redesign
- **Q1:** Data is okay but needs better converter
- **Q2:** Evaluation is possible but noisy
- **Q4:** Minimal experiment shows weak signal (need more data or different approach)
- **Q5:** Generalization is weak (might need domain-specific adapters)

**Action:** Redesign based on findings, run mini-experiment again.

### Red Light: Park This Idea
- **Q1:** Synthetic data is incoherent or trivial
- **Q2:** No evaluation metric works without ground truth
- **Q3:** Literature strongly suggests this doesn't work
- **Q4:** Minimal experiment shows zero effect or negative effect
- **Q5:** LoRA only memorizes training distribution

**Action:** Document learnings, explore alternative (e.g., learned classifier instead of LoRA, or wait for success traces to ground training data).

---

## Open Questions for Isaac (Before Starting Research)

1. **Data source flexibility:** If edges turn out to be weak training signal, can we pivot to using success traces instead (once they exist)? Or is "edges as training data" the core idea?

2. **Model choice:** For minimal experiment, should we test on Mistral 7B (small, fast) or something closer to your actual inference setup (BitNet/larger model)?

3. **Evaluation tolerance:** What's "good enough"? Does LoRA need to improve ranking 50% of the time, or is 20% improvement sufficient to justify the complexity?

4. **Timeline pressure:** Is Handshake LoRA a "nice to have for 2.0" or "must have"? If it's optional, we can take time to get it right. If it's critical path, we should deprioritize risky research.

5. **Failure gracefully:** If research concludes "LoRAs aren't the right tool," is there a backup plan? Or do we need LoRAs specifically?

---

## Next Steps

1. **Review this decomposition** — does it cover your uncertainties? Missing anything?
2. **Answer the open questions** — shapes research priorities
3. **Timeline agreement** — 2 weeks of parallel research okay during data collection?
4. **Assign:** Who does the research? (You? Hermes? Fable for literature search?)

Once research is done, we write a **Research Summary** with findings + recommendation. Then either:
- **Spec the full Handshake LoRA harness** (if green light)
- **Spec an alternative approach** (if red light but found something better)
- **Document & defer** (if inconclusive but interesting)

---

**Version:** 1.0  
**Author:** Claude (design)  
**For:** Isaac (Kitbash roadmap)  
**Date:** July 15, 2026
