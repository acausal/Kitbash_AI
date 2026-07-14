# SPEC: Episode Boundary Annotation Tool v1

**Version:** 1.0  
**Status:** Ready for implementation  
**Target:** Kitbash tool registry (standalone tool)  
**Depends:** dream_bucket.py (append to episodes log)

---

## Purpose

Provide a lightweight mechanism for the agent to explicitly mark transitions between exploratory work (information gathering, context building) and action work (decisions, side effects).

Enables Dream Bucket to track episode boundaries and build queryable dependency graphs during sleep pipeline.

---

## Interface

### Tool Call

```
annotate_episode_boundary(
    phase: str,         # "expl" or "act"
    summary: str,       # Human-readable: "read thermodynamics_general cartridge"
)
```

### Return Value

```json
{
  "episode_id": "expl_20260714_143022_abc123",
  "phase": "expl",
  "summary": "read thermodynamics_general cartridge",
  "timestamp": "2026-07-14T14:30:22Z",
  "status": "logged"
}
```

---

## Behavior

### Preconditions
- Agent is in active query session.
- Dream Bucket is initialized and accepting writes.

### Postconditions
- Record written to `dream_bucket/live/episodes.jsonl` with unique `episode_id`.
- Return value contains the episode_id (for agent to reference in later traces if desired).

### Semantics

**Exploratory Phase (`"expl"`)**
- Agent is gathering information, activating grains, reading cartridges, running searches.
- No durable side effects in the environment.
- Output: learned context, topology, facts.
- Multiple `"expl"` episodes can occur before a single `"act"`.

**Action Phase (`"act"`)**
- Agent is making decisions that produce durable effects.
- Examples: log hypothesis, trigger cartridge crystallization, update Dream Bucket index.
- Effects are already persisted; if session ends, actions are already done.
- An `"act"` episode typically *depends on* prior `"expl"` episodes.

---

## Data Structure

### Episode Record (written to episodes.jsonl)

```json
{
  "episode_id": "expl_20260714_143022_abc123",
  "phase": "expl",
  "summary": "read thermodynamics_general cartridge",
  "timestamp": "2026-07-14T14:30:22Z",
  "session_id": "session_20260714_140000",
  "query_id": "query_002",
  "agent_context": {
    "active_cartridges": ["thermodynamics_general"],
    "grain_count_activated": 3,
    "traces_logged_so_far": 2
  }
}
```

**Fields:**
- `episode_id`: Unique identifier (`{phase}_{timestamp}_{random_suffix}`).
- `phase`: "expl" or "act".
- `summary`: One-line description of episode goal (for readability).
- `timestamp`: ISO UTC when episode was marked.
- `session_id`: Session identifier (if available; optional).
- `query_id`: Current query identifier (if available; optional).
- `agent_context`: Additional context snapshot (optional; used for debugging).

---

## Implementation Notes

### Episode ID Generation

```python
import uuid
from datetime import datetime

def generate_episode_id(phase: str) -> str:
    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = str(uuid.uuid4())[:8]
    return f"{phase}_{now}_{suffix}"
```

### Dream Bucket Integration

Append to new log type:

```python
def log_episode_boundary(
    writer: DreamBucketWriter,
    phase: str,
    summary: str,
    session_id: Optional[str] = None,
    query_id: Optional[str] = None,
    agent_context: Optional[Dict[str, Any]] = None
) -> str:
    """Log episode boundary; return episode_id."""
    episode_id = generate_episode_id(phase)
    record = {
        "episode_id": episode_id,
        "phase": phase,
        "summary": summary,
        "session_id": session_id,
        "query_id": query_id,
        "agent_context": agent_context or {},
    }
    writer.append("episodes", record)  # Append to episodes.jsonl
    return episode_id
```

Update DreamBucketWriter.valid_types to include "episodes":

```python
valid_types = {
    "false_positives", "collisions", "violations", 
    "hypotheses", "traces", "pending_questions", "validated_observations",
    "episodes"  # NEW
}
```

### Latency Considerations

- Tool is non-blocking (queued write via Dream Bucket).
- Expected latency: < 1ms (append to queue).
- No synchronization with agent loop.

---

## Usage Patterns

### Pattern 1: Explicit Transitions (Recommended)

Agent marks phase changes when clear:

```
Query: "What's entropy?"
  1. annotate_episode_boundary("expl", "activating thermodynamics_general")
  2. grain_activation(thermo_grain_id)
  3. text_search("entropy in physics")
  4. [reads results]
  5. annotate_episode_boundary("act", "generating hypothesis about 2nd law")
  6. log_hypothesis("Entropy is measure of disorder...")
```

### Pattern 2: Inferred from Tool Work Type (Fallback)

If agent doesn't mark explicitly, sleep Stage 1.5b infers episodes from tool `work_type` declarations and trace patterns. This ensures *some* structure even if agent is silent.

### Pattern 3: Optional for Lightweight Queries

Short queries may not call `annotate_episode_boundary` at all. They're still traceable via their tool sequence and work_type metadata.

---

## Non-Goals

- **Mandatory episode marking:** Agent can choose whether to use this tool.
- **Automatic phase detection:** We don't infer phase from tool calls; agent is the source of truth.
- **Episode nesting:** Episodes don't nest; one episode per phase transition.
- **Real-time episode queries:** This is write-only; queries happen in sleep stages.

---

## Error Handling

### Invalid phase

```python
if phase not in ("expl", "act"):
    return {
        "status": "error",
        "reason": f"Invalid phase: {phase}. Must be 'expl' or 'act'."
    }
```

### Dream Bucket write failure

```python
if not writer.append("episodes", record):  # Queue full
    return {
        "status": "error",
        "reason": "Dream Bucket queue full; episode not logged."
    }
```

Agent should not crash; backpressure is expected and tolerable. Dream Bucket may drop events if queue is full (documented limitation).

---

## Testing

### Unit Test Example

```python
def test_episode_annotation():
    writer, reader = create_dream_bucket("test_db")
    
    episode_id = log_episode_boundary(
        writer, "expl", "reading docs", 
        session_id="session_1"
    )
    
    assert episode_id.startswith("expl_")
    
    # Read back
    records = list(reader.read_live_log("episodes"))
    assert len(records) == 1
    assert records[0]["phase"] == "expl"
    assert records[0]["summary"] == "reading docs"
```

### Integration Test Example

```python
def test_episode_to_dependency_graph():
    # Mark episodes
    log_episode_boundary(writer, "expl", "phase 1")
    log_trace(writer, "query_001", [...trace chain...])
    log_episode_boundary(writer, "act", "phase 2")
    log_hypothesis(writer, ...)
    
    # Run sleep Stage 1.5b
    builder = EpisodeGraphBuilder(dream_bucket_dir)
    graph = builder.build_graph()
    
    # Verify structure
    assert len(graph["episodes"]) == 2
    assert graph["episodes"]["act_..."]["depends_on"] == ["expl_..."]
```

---

## Open Questions for Isaac

1. **Session/Query ID availability:** Should the tool accept optional `session_id` and `query_id`? Or should it query the current context (Redis state) automatically?

2. **Agent context snapshot:** Should we capture active cartridges/grains at episode boundary? This would enrich the dependency graph but adds overhead. Worth it?

3. **Frequency assumption:** Do you expect agents to call this ~2-5 times per query, or more frequently?

4. **Backward compatibility:** Should this tool be available in Stage 5 recalibration as well, or only during normal queries?

---

## Related Components

- **Dream Bucket** (dream_bucket.py): Accepts append of "episodes" log type.
- **Sleep Stage 1.5b** (episode_dependency_graph builder): Consumes episodes.jsonl.
- **Tool Registry** (kitbash_registry.py): Houses this tool definition.
- **Tool Metadata** (SPEC files): Each tool declares `work_type` to enable inference fallback.
