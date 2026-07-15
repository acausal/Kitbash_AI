# SPEC: Success Signal Integration v1

**Status:** Ready for Implementation  
**Date:** July 15, 2026  
**Priority:** High (gates SLM-v3 post-1.0; must be wired before data collection ends)  
**Effort:** 4–6 hours  
**Dependencies:** Dream Bucket schema, query orchestrator, structured_logger

---

## Overview

Integrate bidirectional success/failure signaling into Dream Bucket. Currently, the system logs only negative signals (violations, false positives, collisions). This spec adds **success traces** as a first-class Dream Bucket artifact, enabling the sleep pipeline to learn what works (via Positive Signal Scorer, Causal Credit Attribution, Success Pattern Miner) in addition to what doesn't.

**Outcome:** By end of data collection window, Dream Bucket contains both violations and successes. Post-1.0, SLM-v3 Stage 3.5 can run bidirectional consolidation (penalize weak paths, reward strong ones).

---

## Scope

### In Scope ✓
- Define schema for `success_traces.jsonl` (mirror of violations.jsonl)
- Implement coherence-based success detection heuristic (automatic, zero-friction)
- Wire success logging into query orchestrator (post-response completion point)
- Define thresholds for coherence check (confidence, violation count, response length)
- Add CLI command to inspect success traces: `slm success-stats` (read-only, debugging)
- Document success signal semantics in Dream Bucket design docs
- Non-destructive: never modify/delete existing violations; only append successes

### Out of Scope ✗
- Explicit user feedback UI (deferred to post-1.0; not needed for data collection)
- Time-based heuristic (Stage 2, post-1.0)
- Success pattern mining (that's a sleep pipeline stage, not this spec)
- Causal credit attribution integration (post-1.0, uses success traces as input)
- Reward edge weights based on success (that's SLM-v3 Stage 3.5, not this spec)
- Multimodal success (audio/visual feedback); text-only for 1.0

---

## Design Decisions

### Success Traces as First-Class Artifact

**Rationale:** Violations are recorded as JSONL events; successes should follow the same contract for consistency. This allows:
- Same Dream Bucket persistence layer
- Same timestamp + trace_id semantics
- Parallel analysis (Sequence Pattern Miner can run on violations OR successes)
- Non-destructive archival (never delete, only archive old traces)

**Storage:** `dream_bucket/live/success_traces.jsonl` (mirrors `violations.jsonl`)

### Coherence-Based Detection (Hybrid Stage 1)

**Rationale:** 
- Automatic (zero user friction during data collection)
- Deterministic (no randomness, reproducible)
- Conservative (errs toward marking as success only when confident)
- Non-blocking (heuristic failure doesn't crash orchestrator; falls through to no-signal case)

**Implementation:** Single `coherence_check()` function that combines:
1. **Violation count** — Dream Bucket violations logged during query execution
2. **MTR confidence** — Top-ranked grain confidence score
3. **Response length** — Minimum output length (rules out "I don't know" cop-outs)
4. **Parse errors** — No runtime exceptions during response generation

**Thresholds (v1, tunable):**
```python
COHERENCE_THRESHOLDS = {
    "max_violations_allowed": 0,          # Zero violations = success candidate
    "min_top_grain_confidence": 0.60,     # MTR top grain must be reasonably confident
    "min_response_length": 100,           # Minimum tokens to avoid one-liners
    "parse_errors_allowed": 0,            # Zero exceptions
}
```

### Trace Structure

Success traces follow F2 schema (same as violations), with added fields:

```json
{
  "trace_id": "succ_tr_20260715_142530_abcd1234",
  "timestamp": "2026-07-15T14:25:30.123456Z",
  "session_id": "session_20260715_142500",
  "query": "What is photosynthesis?",
  "outcome": "success",
  "error_signal": 0.08,
  "violations_during_execution": 0,
  "top_grain_id": 42,
  "top_grain_confidence": 0.72,
  "grains_activated": [42, 137, 89],
  "facts_used": [101, 102, 103],
  "edges_traversed": ["42->137", "137->89"],
  "response_length_tokens": 245,
  "parse_errors": [],
  "coherence_check": {
    "passed": true,
    "violations_check": true,
    "confidence_check": true,
    "length_check": true,
    "errors_check": true
  },
  "metadata": {
    "cartridge": "general_knowledge",
    "hat": "ANALYTICAL",
    "context_l3": "question_answering",
    "context_l4": null
  }
}
```

**Key fields:**
- `outcome: "success"` — terminal state (mirrors violation's dissonance_type)
- `error_signal: [0.0, 1.0]` — inverse of violation severity (0 = perfect, 1 = barely acceptable)
- `coherence_check: {..}` — breakdown of which checks passed (for analysis + debugging)
- `grains_activated`, `facts_used`, `edges_traversed` — ground truth for Sequence Pattern Miner

---

## Implementation

### 1. Schema Extension (Dream Bucket)

**File:** `dream_bucket.py` (or schema module)

**Add dataclass:**
```python
@dataclass
class SuccessTrace:
    trace_id: str
    timestamp: str  # ISO 8601
    session_id: str
    query: str
    outcome: Literal["success"]
    error_signal: float  # [0.0, 1.0]
    violations_during_execution: int
    top_grain_id: int
    top_grain_confidence: float
    grains_activated: list[int]
    facts_used: list[int]
    edges_traversed: list[str]
    response_length_tokens: int
    parse_errors: list[str]
    coherence_check: dict  # {check_name: bool, ...}
    metadata: dict  # cartridge, hat, context_l3, context_l4
```

**Add method to DreamBucket:**
```python
def log_success(self, trace: SuccessTrace) -> None:
    """
    Append success trace to success_traces.jsonl.
    Non-destructive: never modifies existing traces.
    """
    path = self.live_dir / "success_traces.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(asdict(trace)) + "\n")
    structured_logger.get_event_logger("dream_bucket").log(
        "success_trace_logged",
        data={
            "trace_id": trace.trace_id,
            "query": trace.query[:100],
            "error_signal": trace.error_signal,
        }
    )
```

### 2. Coherence Check Heuristic

**File:** New `query_completion_heuristic.py` (or add to query_orchestrator.py)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class CoherenceCheckResult:
    passed: bool
    violations_check: bool
    confidence_check: bool
    length_check: bool
    errors_check: bool
    error_signal: float  # Computed confidence of the success itself

class CoherenceChecker:
    """Determines if a query completion qualifies as a success."""
    
    def __init__(
        self,
        max_violations_allowed: int = 0,
        min_top_grain_confidence: float = 0.60,
        min_response_length: int = 100,
        parse_errors_allowed: int = 0,
    ):
        self.thresholds = {
            "max_violations": max_violations_allowed,
            "min_confidence": min_top_grain_confidence,
            "min_length": min_response_length,
            "parse_errors": parse_errors_allowed,
        }
    
    def check(
        self,
        violations_count: int,
        top_grain_confidence: float,
        response_length: int,
        parse_errors: list[str],
    ) -> CoherenceCheckResult:
        """
        Run coherence checks on query completion.
        
        Args:
            violations_count: # of Dream Bucket violations logged during query
            top_grain_confidence: MTR confidence of top-ranked grain
            response_length: Length of generated response (tokens or chars)
            parse_errors: List of exceptions raised during response generation
        
        Returns:
            CoherenceCheckResult with per-check breakdown + composite error_signal
        """
        violations_ok = violations_count <= self.thresholds["max_violations"]
        confidence_ok = top_grain_confidence >= self.thresholds["min_confidence"]
        length_ok = response_length >= self.thresholds["min_length"]
        errors_ok = len(parse_errors) <= self.thresholds["parse_errors"]
        
        all_passed = violations_ok and confidence_ok and length_ok and errors_ok
        
        # Compute error_signal as inverse of confidence
        # If all checks pass: error_signal = 1 - top_grain_confidence
        # If any check fails: error_signal = 1.0 (maximum penalty)
        error_signal = (
            (1.0 - top_grain_confidence) if all_passed else 1.0
        )
        
        return CoherenceCheckResult(
            passed=all_passed,
            violations_check=violations_ok,
            confidence_check=confidence_ok,
            length_check=length_ok,
            errors_check=errors_ok,
            error_signal=error_signal,
        )
```

### 3. Wire Into Query Orchestrator

**File:** `query_orchestrator.py` (or whichever module handles response completion)

**Location:** Post-response generation, before returning to user

```python
def finalize_response(
    query: str,
    response: str,
    grains_fired: list[int],
    facts_used: list[int],
    edges_traversed: list[str],
    top_grain_confidence: float,
    top_grain_id: int,
    parse_errors: list[str],
) -> str:
    """
    Finalize response: generate, log success/failure signal, return.
    """
    # Count violations logged during this query's execution
    violations_count = dream_bucket.count_recent_violations(
        session_id=session_id,
        time_window_seconds=60,  # Violations logged in last 60s = during this query
    )
    
    # Run coherence check
    coherence_checker = CoherenceChecker()  # Uses default thresholds
    check_result = coherence_checker.check(
        violations_count=violations_count,
        top_grain_confidence=top_grain_confidence,
        response_length=len(response.split()),  # Token proxy
        parse_errors=parse_errors,
    )
    
    # If passed coherence, log success trace
    if check_result.passed:
        trace = SuccessTrace(
            trace_id=generate_trace_id("succ"),
            timestamp=datetime.utcnow().isoformat() + "Z",
            session_id=session_id,
            query=query,
            outcome="success",
            error_signal=check_result.error_signal,
            violations_during_execution=violations_count,
            top_grain_id=top_grain_id,
            top_grain_confidence=top_grain_confidence,
            grains_activated=grains_fired,
            facts_used=facts_used,
            edges_traversed=edges_traversed,
            response_length_tokens=len(response.split()),
            parse_errors=parse_errors,
            coherence_check=asdict(check_result),
            metadata={
                "cartridge": current_cartridge(),
                "hat": current_hat(),
                "context_l3": get_l3_context(),
                "context_l4": get_l4_hat(),
            },
        )
        dream_bucket.log_success(trace)
    else:
        # Log coherence failure as diagnostic (optional, for debugging)
        structured_logger.get_event_logger("query_orchestrator").log(
            "coherence_check_failed",
            data={
                "check_result": asdict(check_result),
                "query": query[:100],
            }
        )
    
    return response
```

### 4. Threshold Tuning & Inspection

**File:** New `success_signal_cli.py` (or add to existing CLI)

```python
def cmd_success_stats(args):
    """
    Read-only: Print success signal statistics.
    Usage: slm success-stats [--since N_DAYS] [--json]
    """
    dream_bucket = DreamBucket()
    success_traces = dream_bucket.read_success_traces(
        since_days=args.since or 7
    )
    
    stats = {
        "total_successes": len(success_traces),
        "avg_error_signal": mean([t.error_signal for t in success_traces]),
        "coherence_check_breakdown": {
            "violations_passed": sum(1 for t in success_traces if t.coherence_check["violations_check"]),
            "confidence_passed": sum(1 for t in success_traces if t.coherence_check["confidence_check"]),
            "length_passed": sum(1 for t in success_traces if t.coherence_check["length_check"]),
            "errors_passed": sum(1 for t in success_traces if t.coherence_check["errors_check"]),
        },
        "avg_response_length": mean([t.response_length_tokens for t in success_traces]),
        "avg_top_grain_confidence": mean([t.top_grain_confidence for t in success_traces]),
    }
    
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"Success Traces (last {args.since or 7} days):")
        print(f"  Total: {stats['total_successes']}")
        print(f"  Avg error_signal: {stats['avg_error_signal']:.3f}")
        print(f"  Coherence breakdown:")
        for check, passed in stats['coherence_check_breakdown'].items():
            print(f"    {check}: {passed} / {stats['total_successes']}")
```

---

## Testing

### Unit Tests

**File:** `TEST-success_signal_integration.py`

```python
def test_coherence_checker_all_pass():
    """All checks pass => success, error_signal ~= 1 - confidence"""
    checker = CoherenceChecker()
    result = checker.check(
        violations_count=0,
        top_grain_confidence=0.72,
        response_length=250,
        parse_errors=[],
    )
    assert result.passed == True
    assert result.error_signal == pytest.approx(1.0 - 0.72, abs=0.01)

def test_coherence_checker_too_many_violations():
    """Violations > max => failure"""
    checker = CoherenceChecker(max_violations_allowed=0)
    result = checker.check(
        violations_count=1,
        top_grain_confidence=0.72,
        response_length=250,
        parse_errors=[],
    )
    assert result.passed == False
    assert result.violations_check == False
    assert result.error_signal == 1.0

def test_coherence_checker_low_confidence():
    """Confidence < threshold => failure"""
    checker = CoherenceChecker(min_top_grain_confidence=0.60)
    result = checker.check(
        violations_count=0,
        top_grain_confidence=0.45,
        response_length=250,
        parse_errors=[],
    )
    assert result.passed == False
    assert result.confidence_check == False

def test_coherence_checker_short_response():
    """Response length < min => failure"""
    checker = CoherenceChecker(min_response_length=100)
    result = checker.check(
        violations_count=0,
        top_grain_confidence=0.72,
        response_length=50,
        parse_errors=[],
    )
    assert result.passed == False
    assert result.length_check == False

def test_dream_bucket_log_success():
    """Success trace appends to JSONL without modifying violations"""
    db = DreamBucket()
    trace = SuccessTrace(...)
    
    db.log_success(trace)
    
    # Verify append-only
    lines = open(db.live_dir / "success_traces.jsonl").readlines()
    assert len(lines) > 0
    last = json.loads(lines[-1])
    assert last["trace_id"] == trace.trace_id
```

### Integration Test

**File:** `TEST-success_signal_e2e.py`

```python
def test_success_signal_e2e():
    """End-to-end: query -> coherence check -> log success -> inspect stats"""
    orchestrator = QueryOrchestrator()
    
    response, metadata = orchestrator.finalize_response(
        query="What is photosynthesis?",
        response="Photosynthesis is the process...",
        grains_fired=[42, 137],
        facts_used=[101, 102],
        edges_traversed=["42->137"],
        top_grain_confidence=0.75,
        top_grain_id=42,
        parse_errors=[],
    )
    
    # Verify success trace was logged
    dream_bucket = DreamBucket()
    traces = dream_bucket.read_success_traces(since_days=0)
    assert len(traces) >= 1
    assert traces[-1].query == "What is photosynthesis?"
    assert traces[-1].outcome == "success"
```

---

## Thresholds (Tunable)

These are **v1 defaults**; all tunable via config or CLI:

| Threshold | Default | Rationale |
|-----------|---------|-----------|
| `max_violations_allowed` | 0 | Zero violations = clean response |
| `min_top_grain_confidence` | 0.60 | Conservative; leaves room for learning |
| `min_response_length` | 100 tokens | Prevents "I don't know" one-liners |
| `parse_errors_allowed` | 0 | No runtime exceptions in success |

**Post-1.0 tuning:** After you collect data, run `slm success-stats` and adjust thresholds based on actual distribution.

---

## Timeline

**Phase 1 (Now → 1.0): Wiring**
- Implement schema, coherence checker, orchestrator integration
- Deploy during data collection window
- Let it run; collect success traces

**Phase 2 (1.0 → 1.1): Inspection**
- Run `slm success-stats` to see what the distribution looks like
- Adjust thresholds if needed (e.g., "we're only marking 5% as success; too strict")
- No behavior change yet; just observation

**Phase 3 (1.1 → 2.0): Integration**
- Post-1.0, build SLM-v3 Stage 3.5
- Use Success Pattern Miner, Positive Signal Scorer, Causal Credit Attribution on success traces
- Apply bidirectional consolidation (penalize violations, reward successes)

---

## Non-Goals & Deferred

- **Explicit user feedback** (Stage 2 Hybrid) — deferred to post-1.0; not needed for data collection
- **Time-based heuristic** — deferred; coherence is sufficient for v1
- **Multimodal signals** (audio, implicit satisfaction) — text-only for 1.0
- **Real-time success prediction** — out of scope; this is logging only
- **Adaptive threshold tuning** — manual post-collection, not automatic

---

## Failure Modes & Mitigations

| Failure | Cause | Mitigation |
|---------|-------|-----------|
| Success traces never logged | Coherence thresholds too strict | Run `slm success-stats`, lower thresholds, re-run |
| False positives (marking failures as success) | Thresholds too loose | Start conservative (current defaults); tighten if needed post-collection |
| Parse errors crash orchestrator | Error handling missing | Wrap coherence check in try-catch; default to no-signal on exception |
| Success traces not accessible post-1.0 | No read API | `dream_bucket.read_success_traces()` + `slm success-stats` CLI |

---

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `dream_bucket.py` | Add SuccessTrace dataclass, log_success() method | ~40 |
| `query_completion_heuristic.py` (new) | CoherenceChecker class | ~80 |
| `query_orchestrator.py` | Call coherence check post-response, log success | ~30 |
| `structured_logger.py` | (no change; reuse existing logging) | 0 |
| `success_signal_cli.py` (new) | `slm success-stats` CLI command | ~40 |
| `TEST-success_signal_integration.py` (new) | Unit + integration tests | ~120 |
| `DREAM_BUCKET_DESIGN.md` | Document success traces schema | ~20 |

**Total new code:** ~330 lines (mostly tests + logging)

---

## Acceptance Criteria

- [ ] SuccessTrace schema implemented + serializes to JSON
- [ ] CoherenceChecker runs without crashing on any input
- [ ] Success traces append to `success_traces.jsonl` (verified via file inspection)
- [ ] `slm success-stats` reads traces and prints stats (no errors)
- [ ] At least 100 success traces collected during 2-week data collection window
- [ ] Zero violations.jsonl data lost; non-destructive archival maintained
- [ ] All tests pass (unit + integration)
- [ ] Documentation updated with success trace semantics

---

## Known Open Questions

1. **What counts as "parse errors"?** Should we include LLM generation timeouts? Currently assumes exceptions only. Needs clarification from orchestrator team.

2. **Cartridge context:** Should we track which cartridge was active during success? Useful for per-cartridge learning post-1.0. Currently captured in metadata; verify this works with multi-cartridge queries.

3. **Session context (L3/L4):** Do we have reliable L3 context at response-finalization time, or does it get cleared? Assuming yes; needs verification.

4. **Success trace retention:** How long to keep success traces before archival? Current assumption: same as violations (non-destructive, never delete). Confirm this aligns with storage policy.

---

**Version:** 1.0  
**Author:** Claude (design)  
**For:** Isaac (Kitbash roadmap)  
**Date:** July 15, 2026
