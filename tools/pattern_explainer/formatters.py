"""Formatting helpers for tools.pattern_explainer (stdlib only)."""
from datetime import datetime, timezone
from typing import List, Optional


def format_percentage(value: float) -> str:
    """0.89 -> '89%'."""
    return f"{round(value * 100)}%"


def format_magnitude(ratio: float) -> str:
    """5.17 -> '5.17x'; 2.0 -> '2.0x' (keep one decimal if trailing zero)."""
    s = f"{ratio:.2f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s + "x"


def format_confidence(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def format_list(items: List) -> str:
    """[42, 137, 89] -> '42, 137, and 89'."""
    items = [str(x) for x in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def format_timestamp(iso_str: str) -> str:
    """Truncate an ISO timestamp to compact form (YYYY-MM-DDTHH:MMZ)."""
    s = iso_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return iso_str
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def _entity_kind(entity_type: str) -> str:
    et = (entity_type or "").lower()
    if et == "grain":
        return "Grain"
    if et == "fact":
        return "Fact"
    return (entity_type or "entity").capitalize()


def format_entity_label(entity_id, entity_type: str = "grain",
                        label: Optional[str] = None) -> str:
    """(42, 'grain') -> 'Grain 42 (query router)' (label optional)."""
    base = f"{_entity_kind(entity_type)} {entity_id}"
    if label:
        return f"{base} ({label})"
    return base


def format_pattern_sequence(sequence: List[str]) -> str:
    """['tokenizer','svo'] -> '[tokenizer -> svo]'."""
    return "[" + " -> ".join(str(s) for s in sequence) + "]"
