"""structured_validator core: validate text against a Lark grammar.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib, Lark,
and Kitbash core's structured_logger (read-only helper). No orchestrator/
engine/redis imports.

v1 is infrastructure: accepts inline EBNF or a .lark file, returns a parse tree
(serialized to a JSON-able dict) or a validation error. No built-in grammars,
registry, or tree transformation yet (v2+).
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from lark import Lark, LarkError

from .parse_result_schema import ParseResult

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("structured_validator")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None

Grammar = Union[str, Path]


def _tree_to_dict(node) -> Any:
    """Recursively serialize a Lark Tree/Token to plain dicts/strings."""
    if hasattr(node, "data"):  # Tree
        return {"data": node.data,
                "children": [_tree_to_dict(c) for c in node.children]}
    return str(node)  # Token (or string leaf)


def _resolve_grammar(grammar: Grammar):
    """Return (grammar_text, grammar_name). Raises FileNotFoundError / ValueError."""
    if isinstance(grammar, Path):
        path = grammar
    elif isinstance(grammar, str) and "\n" not in grammar and grammar.endswith(".lark"):
        path = Path(grammar)
    elif isinstance(grammar, str) and "\n" not in grammar and Path(grammar).exists():
        path = Path(grammar)
    else:
        # Inline EBNF string.
        return grammar, "inline"

    if not path.exists():
        raise FileNotFoundError(f"Grammar file not found: {path}")
    return path.read_text(encoding="utf-8"), path.name


def validate_input(
    text: str,
    grammar: Grammar,
    grammar_start: str = "start",
) -> ParseResult:
    """Validate text against a Lark grammar.

    Args:
        text: Raw input text. Empty string is allowed (most grammars fail).
        grammar: Inline EBNF string, or a path to a .lark file.
        grammar_start: Start rule name (default: "start").

    Returns:
        ParseResult: success flag, serialized parse tree (dict) on success, or
        error string on validation failure.

    Raises:
        ValueError: text is None/not a string, or grammar is invalid EBNF.
        FileNotFoundError: grammar file path does not exist.
    """
    if text is None or not isinstance(text, str):
        raise ValueError(
            "text must be a string (got "
            f"{'None' if text is None else type(text).__name__})"
        )

    grammar_text, grammar_name = _resolve_grammar(grammar)
    if _logger:
        _logger.log(event_type="validation_started",
                    data={"grammar": grammar_name, "input_length": len(text)})

    try:
        parser = Lark(grammar_text, start=grammar_start)
    except Exception as e:  # Lark raises lark.exceptions.GrammarError etc.
        raise ValueError(f"Invalid Lark grammar: {e}") from e

    try:
        tree = parser.parse(text)
        result = ParseResult(
            success=True,
            parse_tree=_tree_to_dict(tree),
            error=None,
            grammar_name=grammar_name,
            input_text=text,
        )
        if _logger:
            _logger.log(event_type="validation_passed", data={"grammar": grammar_name})
    except LarkError as e:
        result = ParseResult(
            success=False,
            parse_tree=None,
            error=str(e),
            grammar_name=grammar_name,
            input_text=text,
        )
        if _logger:
            _logger.log(event_type="validation_failed",
                        data={"grammar": grammar_name, "error": str(e)})
    return result
