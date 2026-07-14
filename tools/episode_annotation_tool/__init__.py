"""tools.episode_annotation_tool package.

Library:
    from tools.episode_annotation_tool import annotate_episode, read_episodes

CLI:
    python -m tools.episode_annotation_tool annotate --phase expl --summary "..." \
        [--session-id ...] [--query-id ...] [--log-path ...]
    python -m tools.episode_annotation_tool read [--log-path ...]

Isolation-safe: stdlib only; writes JSONL (default dream_bucket/live/episodes.jsonl)
matching the SPEC record schema. No import of Kitbash core (dream_bucket.py).
"""
from .core import annotate_episode, read_episodes, generate_episode_id, VALID_PHASES

__all__ = ["annotate_episode", "read_episodes", "generate_episode_id", "VALID_PHASES"]
