"""tools.episode_annotation_tool core (stdlib only; isolation-safe).

Implements the SPEC-episode_annotation_tool_v1 contract: mark exploratory/action
episode boundaries. Instead of importing Kitbash core `dream_bucket.py` (forbidden
by the tools/ Isolation Contract), this writes the episode record as JSONL to a
configurable path (default ``dream_bucket/live/episodes.jsonl``) using only stdlib.
The record schema and episode_id format match the SPEC exactly, so the output is
drop-in compatible with the real Dream Bucket ``episodes`` log type.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

VALID_PHASES = ("expl", "act")
DEFAULT_LOG_PATH = os.path.join("dream_bucket", "live", "episodes.jsonl")


def generate_episode_id(phase: str) -> str:
    """SPEC format: ``{phase}_{YYYYmmdd_HHMMSS}_{uuid8}``."""
    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = str(uuid.uuid4())[:8]
    return f"{phase}_{now}_{suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def annotate_episode(
    phase: str,
    summary: str,
    session_id: Optional[str] = None,
    query_id: Optional[str] = None,
    agent_context: Optional[Dict[str, Any]] = None,
    log_path: str = DEFAULT_LOG_PATH,
    writer=None,
) -> Dict[str, Any]:
    """Mark an episode boundary. Returns a record dict (never raises for
    invalid input — returns a ``status: error`` dict per SPEC error handling).

    If ``writer`` is provided it must expose ``.append(log_type, record)``
    (Dream Bucket compatibility); otherwise records are appended as JSONL to
    ``log_path`` via stdlib. Either way the SPEC record schema is preserved.
    """
    if phase not in VALID_PHASES:
        return {
            "status": "error",
            "reason": f"Invalid phase: {phase!r}. Must be 'expl' or 'act'.",
        }
    if not isinstance(summary, str) or summary == "":
        return {
            "status": "error",
            "reason": "summary must be a non-empty string.",
        }

    episode_id = generate_episode_id(phase)
    record = {
        "episode_id": episode_id,
        "phase": phase,
        "summary": summary,
        "timestamp": _now_iso(),
        "session_id": session_id,
        "query_id": query_id,
        "agent_context": agent_context or {},
    }

    if writer is not None:
        ok = writer.append("episodes", record)
        if not ok:
            return {
                "status": "error",
                "reason": "Dream Bucket queue full; episode not logged.",
            }
    else:
        _append_jsonl(log_path, record)

    return {
        "episode_id": episode_id,
        "phase": phase,
        "summary": summary,
        "timestamp": record["timestamp"],
        "session_id": session_id,
        "query_id": query_id,
        "agent_context": agent_context or {},
        "status": "logged",
    }


def _append_jsonl(path: str, record: Dict[str, Any]) -> None:
    """Append one JSON object as a line; create parent dirs if needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_episodes(log_path: str = DEFAULT_LOG_PATH) -> List[Dict[str, Any]]:
    """Read back all episode records from a JSONL log (for verification/debug)."""
    if not os.path.exists(log_path):
        return []
    out: List[Dict[str, Any]] = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out
