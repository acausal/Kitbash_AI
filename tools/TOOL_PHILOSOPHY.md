# Tool Layer Philosophy — Local Cognitive Stack

**Core idea:** Kitbash tools are building blocks for reproducible, local-first reasoning chains that scale from a sophisticated 90s chatbot to a full cognitive architecture — all runnable on whatever hardware you have.

---

## The Vision

You can extract a working Kitbash instance, freeze its reasoning artifacts, and replay the exact same decision tree on a Raspberry Pi running only:
- The tool stack (atomic, deterministic scripts)
- A deterministic companion layer (rules, grammar, no learning)
- Extracted traces (what ran, when, with what inputs/output)

**Same reasoning, different hardware. No cloud, no subscriptions, no magic.**

---

## Design Principles

### 1. Reproducibility Over Performance
- Same input → same output, always
- No hidden state, no randomness (or explicitly seeded)
- Floating-point surprises documented
- Tool behavior is testable, verifiable, versioned

### 2. Text as the Interface
- Tools talk via JSON, CSV, structured text
- Composition happens via pipes/redirection (POSIX style)
- Intermediate formats are human-readable (debuggable)
- No binary protocols, no opaque data structures

### 3. Stateless, Atomic Functions
- Each tool does one thing well
- No shared mutable state between tools
- Tool failures are loud and clear (exit codes, error messages)
- Composition is explicit (you see the data flow)

### 4. Local-First, Hardware-Agnostic
- No cloud dependencies (APIs, subscriptions, online services)
- Graceful degradation (tools work on constrained hardware)
- Predictable resource usage (CPU/memory/time known upfront)
- Extractable and reproducible (no GPU magic, no model randomness)

### 5. Scaling is Configuration, Not Architecture
- Same tool stack works for:
  - A 90s chatbot (rules + simple lookup)
  - A modern agent (rules + learned components)
  - A full Kitbash instance (sleep, learning, dream bucket)
- What changes is *which tools you invoke*, *how often*, *in what order*
- The stack itself is always the same

---

## What This Means for Tool Design

### ✅ DO:
- Design tools as pure, deterministic functions
- Use stdin/stdout/stderr (POSIX discipline)
- Emit structured output (JSON, CSV, line-oriented)
- Log tool invocation traces (for replay/debugging)
- Version specs (SPEC-tool_vN.md); track evolution
- Keep dependencies minimal (stdlib + lightweight PyPI)
- Test with explicit inputs/outputs (no randomness)

### ❌ DON'T:
- Hide state in files or databases (use explicit I/O)
- Introduce randomness without seeding
- Create tool interdependencies (tools are independent)
- Rely on external services (APIs, cloud, online models)
- Assume specific hardware (GPU, specific CPU, high memory)
- Make tools "smart" (that's the orchestrator's job)

---

## Tool Categories

### Core Data Plumbing
*Pure transformation, no domain logic*

- **JSON query/filter** — extract fields, filter, transform
- **CSV operations** — parse, filter, transform rows
- **Text search** — pattern matching, line operations
- **Output formatting** — convert between formats, pretty-print
- **Line filtering** — dedup, sort, unique

### Temporal & Logical
*Deterministic, reproducible operations*

- **DateTime utilities** — parse, format, calculate, normalize
- **Math evaluation** — arithmetic, transcendentals (deterministic)
- **Unit conversion** — temperature, distance, weight (deterministic tables)
- **Logic evaluation** — boolean operations, rule application

### Domain-Specific
*Kitbash-specific, but still reproducible*

- **Corpus querying** — search Dream Bucket, grains (deterministic ranking)
- **Fact extraction** — entities, triples, relationships
- **Fact lookup / ranking** — apply MTR or confidence scoring
- **Trace serialization** — record tool invocations for replay
- **Deterministic sampling** — seeded RNG for reproducible variation

### Discovery & Assembly
*Helping humans reason about the stack*

- **Tool introspection** — list available tools, contracts, specs
- **Reasoning trace viewer** — visualize which tools ran, in what order
- **Composition validator** — check if tool chains are valid

---

## Reproducibility & Extraction

### Reasoning Artifact = Frozen Tool Chain
When Kitbash makes a decision, you can extract:

1. **Input state** (query, time, context snapshot)
2. **Tool sequence** (which tools fired, in order)
3. **Tool inputs** (what each tool saw)
4. **Tool outputs** (what each tool produced)
5. **Composition trace** (how outputs fed into next tool's input)

This entire artifact is **deterministic and reproducible** on any machine with the tool stack.

### Replay on Potato Hardware
Take that artifact + the tool stack, and you can:
- Run it on a Raspberry Pi (no GPU needed)
- Run it offline (no cloud services)
- Run it again (same outputs, guaranteed)
- Debug it (every intermediate step is visible)
- Modify it (tweak a tool output, see downstream effects)

---

## Scaling Examples

### Level 1: 90s Chatbot
- Tools: Text search, pattern matching, simple lookup
- No learning, no state beyond conversation history
- Deterministic responses based on rules + corpus
- Runs on CPU, ~10MB RAM

### Level 2: Modern Agent
- Tools: Above + math, fact extraction, temporal reasoning
- Simple learned components (trained grains, cached MTR rankings)
- Traces reasoning steps (what it looked up, why)
- Runs on CPU or small GPU, ~500MB RAM

### Level 3: Full Kitbash
- Tools: All of the above + corpus querying, sleep consolidation, trace serialization
- Full learned stack (grains, procedural edges, sleep-trained artifacts)
- Persistent state (Dream Bucket, Redis bus)
- Extracts and replays decision chains
- Runs on modest hardware (GTX 1060+, or multi-machine via Redis bus)

**The tool stack is the same at all levels. What changes is configuration and composition.**

---

## Implications for Tool Design

### No Tool Should Require:
- Internet access (except explicit "fetch external data" tool)
- GPU or specialized hardware (graceful degradation)
- Long-running background processes
- Stateful services (use Redis as shared blackboard, not as hidden state)

### Every Tool Should Have:
- A CLI interface (testable standalone)
- Deterministic behavior (seeded if randomness is needed)
- Clear error semantics (exit codes, error messages)
- Documented input/output formats (JSON schema, examples)
- Explicit scope (SPEC-tool_vN.md with non-goals)

### Every Reasoning Chain Should Be:
- Extractable (record what ran, in order)
- Reproducible (run it again, same results)
- Debuggable (inspect intermediate outputs)
- Modifiable (tweak a tool, rerun, see effects)

---

## Why This Matters

**Traditional ML/AI stacks:**
- Hidden state in weights
- Randomness by design (sampling, dropout)
- Cloud dependency (inference APIs)
- Opaque decision-making (hard to debug)
- Hardware-specific (GPU for production)

**Kitbash tool stack:**
- Explicit state (JSON, Redis, files)
- Reproducible behavior (seeded randomness, deterministic tools)
- Local-first (no cloud dependency)
- Transparent reasoning (every tool invocation is visible)
- Hardware-agnostic (works on potato, scales to multi-machine)

You're building **cognitive infrastructure as open, reproducible, composable tools** instead of opaque neural nets.

---

## Design Checklist for New Tools

Before spec-ing a new tool:

- [ ] Can it run deterministically (same input → same output)?
- [ ] Can it be expressed as a CLI tool?
- [ ] Does it compose via stdin/stdout (text interface)?
- [ ] Is its scope clearly defined (SPEC with non-goals)?
- [ ] Can it run on CPU-only hardware?
- [ ] Can its reasoning be traced and logged?
- [ ] Are its dependencies lightweight (stdlib + minimal PyPI)?

If the answer to any is "no," either redesign or defer.

---

**Last updated:** 2026-07-13  
**Philosophy owner:** Isaac (Kitbash AI)  
**For:** Tool stack designers, future contributors, anyone building cognitive systems the local-first way
