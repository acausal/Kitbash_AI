# SPEC: Document Addressing (RLM + Sage-Wiki Synthesis)

**Date:** 2026-07-10
**Status:** APPROVED FOR IMPLEMENTATION — execute steps in order, no skipping
**Audience:** implementing model(s). Read the whole document before writing any code. Working rules apply: surgical edits, TEST-/DIAGNOSTIC- prefixes for non-shipping files, paste executed test output — claimed success is not success.
**Blocking:** nothing. This is independent of the Phase 5 critical path (Redis bus wiring, Mutation 1, Mutation 2) and may proceed in parallel with it. Do not let this spec's work block or get blocked by Phase 5 wiring sessions.
**Source:** `MAGPIE_PILE_2.md` Entry 4 (Document Addressing), synthesizing `MAGPIE_PILE.md` Entry 2 (Recursive Language Models) and Entry 4 (Sage-Wiki). Read Entry 4 in full before starting — this spec is the executable form of that entry, not a replacement for its reasoning.

---

## 1. Current State (verify before writing code)

Kitbash's cartridge/grain/fact system operates on atomized facts, not addressable documents. `kitbash_cartridge.py`'s `assemble_context()` builds LLM context by adding discrete `fact_id`-keyed records until a word-count-estimated token budget (default 3300) is exceeded, then stops. There is no raw-document store with internal addressable structure (sections, chunks, offsets) — documents get dissolved into atomic facts at ingestion and the original structure does not survive.

**Verify this claim before building anything**: grep the tree for any existing document-chunk store, FTS index, or section-addressable content model. `PROJECT_CART_LOADING_SPEC.md` and `kitbash_registry.py` are the most likely places something like this could already exist partially. If something does exist, stop and report it — do not build a duplicate.

**Why this matters now**: the target model has a very small context window. The existing `assemble_context()` truncation strategy (add facts until budget exceeded) does not scale to "address a specific document on demand" — it was never designed for that use case, it was designed for fact-level context assembly.

## 2. Target Architecture

Two new layers, plus a testing protocol that must be followed in order. This is new construction, not a refactor of the cartridge/grain system — keep the two systems structurally separate. A fact may cite a document chunk ID; a document chunk does not become a fact.

### 2.1 Storage Layer

A new document store, separate from cartridges:
- Raw document content, chunked with stable, addressable IDs (section/paragraph/line-range keyed — not just a single blob per document).
- SQLite FTS5 keyword index over chunks (ships with SQLite, zero new dependency).
- Embeddings: **deferred**. Ship FTS5-only first (see §4 Step 1 acceptance). Vector search is an explicit later step, not part of this pass, unless Step 1's own testing shows keyword-only search is inadequate for realistic queries — if so, stop and report before adding embeddings, don't add them preemptively.

### 2.2 Navigation Layer

A fixed, small tool-calling surface the inference engine can call against the storage layer:
- `search(query) -> ranked chunk_ids` (FTS5 lookup)
- `get_chunk(document_id, chunk_id) -> content`
- `list_chunks(document_id) -> [chunk_ids]`
- `grep(document_id, pattern) -> matching chunk_ids`

This is a narrower, more constrained version of the RLM paper's free-form Python REPL approach — deliberately, for reliability at small model scale. See §3 for why both this and the free-form alternative get tested before either is committed to.

### 2.3 Recursive Sub-Call Handling

For chunks that need actual reasoning (not just lookup), spawn a fresh sub-call scoped to just that chunk — RLM's core mechanism, each sub-call gets a clean context window, avoiding "middle-token collapse" from stuffing everything into one long context.

**Guardrails, not optional**: cap recursion depth and cap sub-call count per top-level query from the start. RLM's own paper flags high-variance outlier cost (3x+) as a known failure mode of ungated recursion. Starting caps: depth 1, sub-call budget TBD — see §3, these get set from real trajectory data collected during large-model validation, not guessed at before any data exists.

### 2.4 Tracing

Every chunk pull (via any of the four tools in §2.2) gets logged to Dream Bucket the same way fact/grain accesses already are — this is what lets a future sleep stage learn which documents are productively addressed vs. never hit. Reuse the existing `log_trace()` pattern from `dream_bucket.py`; do not invent a parallel logging mechanism.

## 3. Testing Protocol — Larger Model First (mandatory sequencing)

This is a deliberate decision, not a suggestion: **do not begin capacity-tuning against the small target model until the design has been validated end-to-end against a larger model.**

Rationale: if a design fails on a large model, the design is wrong (bad tool surface, bad chunking granularity, bad prompt structure) — no amount of small-model capacity work fixes a bad design. If a design works cleanly on a large model but fails on the small target model, the gap is attributable specifically to model capacity, and only then is it worth optimizing for.

**Required order:**

1. Implement §2.1 (storage) and §2.2 (fixed tool surface) fully.
2. Validate §2.2 end-to-end against a larger model (ask which model is available/preferred for this pass before assuming — do not default to whatever is already configured for the small-model path).
3. **Also** implement and validate a free-form code-generation variant (closer to RLM's actual mechanism — the model writes small Python/query snippets against the storage layer rather than calling fixed tools) against the same larger model. Compare success rate and behavior against the fixed-tool-surface variant from step 2. Report both results — do not skip this comparison and default to the fixed surface; it was chosen as a hedge for small-model reliability, not because it's known to be better.
4. Based on steps 2–3's results, decide which navigation approach (fixed tools, free-form, or a specific hybrid) to carry forward. Report the decision and reasoning before proceeding — this is a checkpoint, not a step to blow through.
5. Only after step 4: run the chosen approach against the actual small target model. Failures here are capacity findings, not design findings — report them as such, and do not silently redesign the interface to work around a capacity gap without flagging it first.

## 4. Build Checklist (strict order; acceptance criteria are executed test output)

**Step 0 — Confirm the gap.**
Grep-verify §1's claim (no existing document-chunk store). Report findings before proceeding.
*Acceptance:* grep output pasted, confirming no pre-existing overlapping system, or a report if one is found (in which case: stop, do not proceed to Step 1 until this is resolved with the project owner).

**Step 1 — Storage layer.**
Build the document store: chunked content, stable addressable chunk IDs, SQLite FTS5 index. New files, e.g. `document_store.py` + `TEST-document_store.py`.
*Acceptance:* round-trip test — ingest a real multi-section document, retrieve specific chunks by ID, run keyword searches and confirm ranked, relevant chunk IDs come back. Paste executed output.
*Chunking note:* Step 1 ships **format-agnostic chunking** (blank-line paragraph splits + stable line-range keys), deliberately — documents here are not guaranteed Markdown and format-aware chunking is unsafe on untyped text. A heading-aware Markdown strategy (Option A) is a legitimate FUTURE option, but **gated on an explicit "is this source verifiably Markdown?" check** at ingest — it is NOT a general replacement for B. Do not silently swap B for A without that gate.

**Step 2 — Fixed tool surface.**
Implement the four tools from §2.2 as callable functions/methods against the Step 1 storage.
*Acceptance:* unit tests for each tool in isolation (stub or real storage), all passing, output pasted.

**Step 3 — Large-model validation, both variants (§3, steps 2–4).**
Wire the fixed tool surface AND a free-form code-generation variant against a larger model. Run both on realistic multi-chunk documents requiring at least one recursive sub-call to answer correctly. Report success/failure per variant with example transcripts, not just pass/fail counts.
*Acceptance:* executed transcripts from both variants pasted; explicit recommendation on which to carry forward, with reasoning.

**Step 4 — Recursion guardrails.**
Set concrete depth/sub-call caps based on §3's trajectory data (not the placeholder numbers in §2.3).
*Acceptance:* caps documented with the data that justified them; a test demonstrating the cap actually stops runaway recursion (e.g. a pathological document/query engineered to try to over-recurse).

**Step 5 — Wiring decision.**
Decide whether this becomes a new `InferenceEngine` cascade slot or a tool available within an existing engine call. **This is a decision point — propose the tradeoffs and ask before committing**, do not pick unilaterally; this affects the socket map and how the orchestrator cascade is structured.
*Acceptance:* written recommendation with tradeoffs; proceed to wiring only after explicit go-ahead.

**Step 6 — Wire per Step 5's decision.**
Implement the chosen integration point.
*Acceptance:* end-to-end query through the real orchestrator path that requires document addressing to answer correctly, output pasted.

**Step 7 — Dream Bucket tracing (§2.4).**
Wire chunk-pull logging using the existing `log_trace()` pattern.
*Acceptance:* executed query produces a trace record with document/chunk references, shape consistent with existing fact/grain traces, output pasted.

**Step 8 — Small-model pass.**
Run the Step 5-chosen, Step 4-capped approach against the actual small target model (whatever's already configured for the production path).
*Acceptance:* results reported honestly, including failures — this step is measurement, not a bar to clear. If the small model can't reliably use the approach, report the gap precisely (what fails, how often, in what way) rather than papering over it or silently loosening the guardrails from Step 4 to make it pass.

## 5. Contract Test Specification (for a permanent `TEST-document_addressing_contract.py`)

Once Steps 1–7 are complete, consolidate into a permanent contract suite, minimum assertions:
1. Storage round-trip: ingest, retrieve by chunk ID, search returns relevant ranked results.
2. Recursion cap enforced under an adversarial/pathological input.
3. Trace logging fires on every chunk pull, shape matches existing trace conventions.
4. Whichever navigation approach was chosen (Step 5) answers a realistic multi-chunk query correctly end-to-end through the real orchestrator path.
5. Failure isolation: a malformed document or storage error does not crash the orchestrator — same loud-failure-not-silent-failure discipline as the rest of the system (`feed.log_error`, not a bare `except: pass`).

## 6. Out of Scope (explicitly, so nobody "improves" en route)

No changes to the cartridge/grain/fact system — this is a new, structurally separate layer. No Redis bus dependency — this must work without it, since Redis bus wiring is a separate, currently-blocked track. No vector embeddings in this pass (§2.1). No hardware upgrade decisions — if Step 8 reveals a capacity gap, report it; do not treat it as license to recommend or assume a hardware change, that decision belongs to the project owner. No redesigning the navigation approach mid-implementation to "improve" on the Step 4 decision without flagging it as a checkpoint first, same discipline as the rest of the project's scope-lock rule.

---
*Written against read-only project state as of 2026-07-10. If `kitbash_cartridge.py`, `kitbash_registry.py`, or `PROJECT_CART_LOADING_SPEC.md` have changed since, re-verify §1 before executing Step 0.*
