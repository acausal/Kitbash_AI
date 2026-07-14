# SPEC: Structured Input Validator v1

## Purpose
Generic validation framework for structured input using Lark grammar definitions. Accepts user-provided grammars (inline or from file) and validates raw input against them, returning parse trees or validation errors. Designed as a pluggable LEGO piece; concrete domain-specific grammars deferred until specific use cases emerge. v1 is infrastructure; actual grammars built on-demand.

## Scope

### In Scope
- Accept raw input text + a Lark grammar (inline string or file path)
- Parse input against grammar using Lark
- Return parse tree (successful parse) or validation error (parse failure)
- Support multiple grammar sources: inline EBNF, file path, grammar name from registry
- CLI entry point: `python -m tools.structured_validator <input.txt> --grammar <grammar.lark>`
- Library API: `validate_input(text: str, grammar: str | Path) -> ParseTree | ValidationError`
- Structured logging via `structured_logger.py`

### Non-Goals (v1)
- Built-in domain-specific grammars (those come later as use cases emerge)
- Grammar composition or inheritance (simple flat grammars only)
- Transformation of parsed output (return parse tree as-is)
- Error recovery or fuzzy matching
- Grammar optimization or caching (may add in v2)

## Data Structures

### ParseResult (dataclass)
```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ParseResult:
    success: bool              # True if parse succeeded
    parse_tree: Optional[Any]  # Lark parse tree (if success=True)
    error: Optional[str]       # Error message (if success=False)
    grammar_name: str          # Which grammar was used
    input_text: str            # Original input
```

## API Contract

### Library API
```python
from tools.structured_validator import validate_input

# Using inline grammar
grammar = """
    ?start: greeting " " name
    greeting: "hello" | "hi" | "hey"
    name: /[A-Z][a-z]+/
"""
result = validate_input("hello Alice", grammar)
# result.success = True, result.parse_tree = Tree(...)

# Using grammar from file
result = validate_input("hello Alice", "grammars/greeting.lark")
# result.success = True (if grammar/greeting.lark exists)

# Failed parse
result = validate_input("goodbye Alice", grammar)
# result.success = False, result.error = "Expected 'hello' or 'hi' or 'hey'"
```

**Signature:**
```python
def validate_input(
    text: str,
    grammar: str | Path,
    grammar_start: str = "start"
) -> ParseResult:
    """
    Parse input text against a Lark grammar.
    
    Args:
        text: Raw input text to validate
        grammar: Either inline EBNF grammar string or path to .lark file
        grammar_start: Start rule name (default: "start")
    
    Returns:
        ParseResult with success flag, parse tree (if success), or error message
    
    Raises:
        ValueError: Text is None or not a string
        ValueError: Grammar is invalid EBNF or file not found
        FileNotFoundError: Grammar file path does not exist
    """
```

### CLI
```bash
python -m tools.structured_validator input.txt --grammar "grammars/greeting.lark"
python -m tools.structured_validator input.txt -g inline_grammar.txt
python -m tools.structured_validator input.txt --grammar-string 'greeting: "hello"'
python -m tools.structured_validator input.txt --output result.json
```

**Behavior:**
- Read input text from file
- Load grammar from file, inline string, or registry name
- Parse and validate
- Write JSON result (default: stdout)
- Exit code 0 on success, 1 on validation failure, 2 on grammar/file error
- Print summary to stdout: `Validation: <input> against <grammar> → <PASS|FAIL>`

**Output format (JSON):**
```json
{
  "success": true,
  "grammar_name": "greeting.lark",
  "parse_tree": {
    "data": "greeting",
    "children": ["hello"],
    "meta": {...}
  },
  "error": null,
  "input_text": "hello Alice"
}
```

Or on failure:
```json
{
  "success": false,
  "grammar_name": "greeting.lark",
  "parse_tree": null,
  "error": "Expected 'hello', 'hi', or 'hey'; got 'goodbye'",
  "input_text": "goodbye Alice"
}
```

## Implementation Notes

### Lark Integration
- Instantiate parser: `parser = Lark(grammar, start=grammar_start)`
- Parse input: `tree = parser.parse(text)`
- On ParseError: catch and return error message

```python
from lark import Lark, ParseError
from tools.structured_validator import ParseResult

def validate_input(text: str, grammar: str | Path, grammar_start: str = "start") -> ParseResult:
    if text is None or not isinstance(text, str):
        raise ValueError("Text must be a string")
    
    # Determine if grammar is inline EBNF or file path
    if isinstance(grammar, Path) or (isinstance(grammar, str) and "\n" not in grammar and grammar.endswith(".lark")):
        # Load from file
        try:
            grammar_path = Path(grammar)
            grammar_text = grammar_path.read_text()
            grammar_name = grammar_path.name
        except FileNotFoundError:
            raise FileNotFoundError(f"Grammar file not found: {grammar}")
    else:
        # Inline grammar
        grammar_text = grammar
        grammar_name = "inline"
    
    # Parse
    try:
        parser = Lark(grammar_text, start=grammar_start)
    except Exception as e:
        raise ValueError(f"Invalid Lark grammar: {e}")
    
    try:
        tree = parser.parse(text)
        return ParseResult(
            success=True,
            parse_tree=tree,
            error=None,
            grammar_name=grammar_name,
            input_text=text
        )
    except ParseError as e:
        return ParseResult(
            success=False,
            parse_tree=None,
            error=str(e),
            grammar_name=grammar_name,
            input_text=text
        )
```

### Grammar Sources
- **Inline:** Pass EBNF string directly
- **File:** Pass path to `.lark` file
- **Registry (v2+):** Named grammars from a central repo (e.g., `grammar_name="query_format_v1"`)

### Logging
```python
from structured_logger import get_event_logger
logger = get_event_logger("structured_validator")

logger.log(event_type="validation_started", data={"grammar": grammar_name, "input_length": len(text)})
if result.success:
    logger.log(event_type="validation_passed", data={"grammar": grammar_name})
else:
    logger.error(event_type="validation_failed", data={"grammar": grammar_name, "error": result.error})
```

## Testing & Validation

### Manual Test Cases
1. **Simple inline grammar:** "hello Alice" against greeting grammar → success, parse tree
2. **Grammar from file:** Load `.lark` file, parse valid input → success
3. **Invalid input:** "goodbye Alice" against greeting grammar → failure, error message
4. **Missing file:** Reference nonexistent `.lark` → FileNotFoundError
5. **Invalid grammar syntax:** Malformed EBNF → ValueError with details
6. **Empty input:** Empty string → parse failure (most grammars require content)
7. **None input:** Pass None → ValueError
8. **Complex grammar:** Multi-rule grammar with nesting → parse tree captures structure
9. **Grammar with custom start rule:** `grammar_start="rule_name"` → uses correct rule
10. **JSON output:** Result serializes to valid JSON (including parse_tree)
11. **Exit codes:** Success=0, validation fail=1, grammar error=2
12. **CLI: file + grammar args:** Correctly reads both input and grammar sources

### Acceptance Criteria
- Library function imports and calls cleanly
- CLI works with file input + grammar file
- Inline grammar parsing works
- File-based grammar loading works
- Valid input against grammar → success + parse tree
- Invalid input against grammar → failure + error message
- Grammar errors caught and reported clearly
- ParseResult serializes to JSON
- Exit codes are correct (0/1/2)
- Pasted terminal output demonstrating all test cases

## Module Structure
```
tools/structured_validator/
  __init__.py            # exports validate_input()
  core.py                # validate_input() implementation
  cli.py                 # argparse CLI
  parse_result_schema.py # ParseResult dataclass
  grammars/             # (future) directory for .lark grammar files
  README.md              # usage docs
```

## Dependencies
- `lark` (PyPI; pure Python parser library, lightweight)

## Grammar Storage Strategy (v2+)
As use cases emerge and you collect grammars, create subdirectories:
```
tools/structured_validator/grammars/
  greeting.lark          # greeting format
  query_format_v1.lark   # structured query format
  action_log.lark        # log entry format
  ...
```

Registry (v2+):
```python
# tools/structured_validator/grammar_registry.py
GRAMMAR_REGISTRY = {
    "greeting": "grammars/greeting.lark",
    "query": "grammars/query_format_v1.lark",
    ...
}
```

Then CLI: `python -m tools.structured_validator input.txt --grammar query`

## Future Extensions (v2+)
- **Grammar registry:** Named grammars stored in `grammars/` subdirectory
- **Grammar composition:** Combine multiple grammars or import rules
- **Parse tree transformation:** Convert parse tree to structured data (JSON, dataclass)
- **Error recovery:** Partial parses, fuzzy matching for typos
- **Grammar optimization:** Cache compiled Lark parsers
- **Domain-specific grammars:** Collect grammars for common input formats (query DSLs, log formats, config files)
- **Grammar validation:** Check that a grammar is valid before use
- **Trace/debug mode:** Show parse steps for troubleshooting
- **Integration with input sieve:** Use as optional validation stage after tokenization/NER/SVO

## Done When
- `tools/structured_validator/__init__.py` exports `validate_input()` and `ParseResult`
- `tools/structured_validator/core.py` implements validation logic
- `tools/structured_validator/cli.py` implements CLI via argparse
- `tools/structured_validator/parse_result_schema.py` defines ParseResult dataclass
- `tools/structured_validator/README.md` documents API, grammar syntax, examples
- All 12 manual test cases pass with pasted output
- JSON output is valid and complete
- Exit codes are correct (0/1/2)
- `tools/README.md` updated to list structured_validator
- **NOTE:** Concrete grammars deferred until use cases emerge. Spec is infrastructure only; first grammar examples added when needed.
