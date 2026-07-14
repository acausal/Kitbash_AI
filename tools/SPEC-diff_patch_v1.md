# SPEC: Diff/Patch Tool v1

**Version:** 1.0  
**Status:** Ready for implementation  
**Target:** Kitbash tool registry (standalone tool)  
**Depends:** stdlib `difflib` only  
**Priority:** Tier 2 (elevated for file editing + Dream Bucket versioning)

---

## Purpose

Generate unified diffs between two texts and apply patches. Core to iterative file editing, change tracking, and efficient archival (store diffs instead of full snapshots).

**Applications:**
- Query-time editing: generate diffs instead of full file rewrites
- Dream Bucket archival: store only diffs, reconstruct versions on demand
- Stage 5 recalibration: approve/reject code changes via diff review
- Post-1.0 self-modification: Kitbash proposes diffs to its own code

---

## Interface

### Tool Call: Generate Diff

```
diff_generate(
    text_a: str,          # Original text
    text_b: str,          # Modified text
    context_lines: int = 3,  # Lines of context around changes (default 3)
)
```

### Return Value: Unified Diff

```json
{
  "status": "success",
  "operation": "diff",
  "diff": "--- original\n+++ modified\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n",
  "num_changes": 1,
  "text_a_size": 5,
  "text_b_size": 5
}
```

### Tool Call: Apply Patch

```
diff_apply(
    text: str,            # Original text
    patch: str,           # Unified diff (from diff_generate or external)
)
```

### Return Value: Patched Text

```json
{
  "status": "success",
  "operation": "apply",
  "result": "a\nB\nc\n",
  "text_size": 5
}
```

### Error Cases

```json
{
  "status": "error",
  "operation": "apply",
  "reason": "Patch does not apply cleanly: hunk at line 10 failed",
  "text": "..."
}
```

---

## Semantics

### Unified Diff Format

Standard unified diff (RFC 3881):
```
--- path/to/original
+++ path/to/modified
@@ -start,count +start,count @@
 context line
-removed line
+added line
 context line
```

**Elements:**
- `---` / `+++`: file headers (can be omitted; tool ignores them)
- `@@`: hunk header with line numbers and counts
- ` ` (space): context (unchanged) line
- `-`: removed line
- `+`: added line
- No leading space on empty lines; they appear as just `-` or `+`

### Context Lines

`context_lines` parameter controls how many unchanged lines appear around each change:

```
diff_generate(text_a, text_b, context_lines=1)  # Minimal context
diff_generate(text_a, text_b, context_lines=3)  # Standard (default)
diff_generate(text_a, text_b, context_lines=0)  # No context
```

More context makes diffs more readable and robust to nearby changes; less context saves space.

### Patch Application

`diff_apply` attempts to apply a patch to text:
1. Parse patch into hunks
2. For each hunk: locate context lines in text, verify match
3. If context matches, insert/remove lines
4. If context doesn't match, try fuzzy matching (nearby lines)
5. If still no match, return error with line number

**Fuzz factor:** Allow 1 line of context to be missing if others match (tolerance for slight drift).

### Special Cases

**Empty files:**
```
diff_generate("", "hello")
→ Diff shows addition of "hello"

diff_generate("hello", "")
→ Diff shows removal of "hello"
```

**Binary data:**
The tool works on text only. If given binary (null bytes, non-UTF8), return error.

**Very large diffs:**
No hard limit, but very large texts (>10MB) may be slow. Tool still works.

---

## Implementation Notes

### Algorithm: Generate Diff

Use `difflib.unified_diff()`:

```python
import difflib

def diff_generate(text_a: str, text_b: str, context_lines: int = 3) -> dict:
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    
    diff_lines = difflib.unified_diff(
        lines_a, lines_b,
        lineterm='',
        n=context_lines  # context lines
    )
    
    diff_text = '\n'.join(diff_lines)
    num_changes = sum(1 for line in diff_lines if line.startswith(('+', '-')))
    
    return {
        "status": "success",
        "operation": "diff",
        "diff": diff_text,
        "num_changes": num_changes,
        "text_a_size": len(text_a),
        "text_b_size": len(text_b)
    }
```

### Algorithm: Apply Patch

Use `difflib.SequenceMatcher` or manual hunk parsing:

```python
def diff_apply(text: str, patch: str) -> dict:
    try:
        # Parse patch into hunks
        hunks = _parse_unified_diff(patch)
        
        lines = text.splitlines(keepends=True)
        offset = 0  # Track line number shifts due to additions/deletions
        
        for hunk in hunks:
            start = hunk['start'] - 1 + offset  # Convert to 0-indexed
            
            # Verify context matches
            for i, context_line in enumerate(hunk['context_before']):
                if lines[start + i] != context_line:
                    # Try fuzzy match (search nearby)
                    if not _fuzzy_match(lines, start, hunk):
                        raise ValueError(f"Patch does not apply at line {start + 1}")
            
            # Apply: remove old lines, insert new lines
            old_count = hunk['old_count']
            new_lines = hunk['new_lines']
            
            lines[start:start + old_count] = new_lines
            offset += len(new_lines) - old_count
        
        return {
            "status": "success",
            "operation": "apply",
            "result": ''.join(lines),
            "text_size": len(''.join(lines))
        }
    except Exception as e:
        return {
            "status": "error",
            "operation": "apply",
            "reason": f"Patch does not apply cleanly: {str(e)}",
            "text": text
        }
```

### Hunk Parsing

Parse `@@` headers to extract line numbers and counts:

```python
def _parse_unified_diff(patch: str):
    """Parse unified diff into structured hunks."""
    hunks = []
    current_hunk = None
    
    for line in patch.split('\n'):
        if line.startswith('@@'):
            # @@ -start,count +start,count @@
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                current_hunk = {
                    'old_start': int(match.group(1)),
                    'old_count': int(match.group(2)) or 1,
                    'new_start': int(match.group(3)),
                    'new_count': int(match.group(4)) or 1,
                    'old_lines': [],
                    'new_lines': [],
                    'context_before': []
                }
                hunks.append(current_hunk)
        elif line.startswith('-'):
            current_hunk['old_lines'].append(line[1:] + '\n')
        elif line.startswith('+'):
            current_hunk['new_lines'].append(line[1:] + '\n')
        elif line.startswith(' '):
            current_hunk['context_before'].append(line[1:] + '\n')
    
    return hunks
```

---

## Data Structure

### Input Schema (Generate)

```json
{
  "operation": "diff",
  "text_a": "hello\nworld\n",
  "text_b": "hello\nWORLD\n",
  "context_lines": 3
}
```

### Input Schema (Apply)

```json
{
  "operation": "apply",
  "text": "hello\nworld\n",
  "patch": "--- original\n+++ modified\n@@ -1,2 +1,2 @@\n hello\n-world\n+WORLD\n"
}
```

### Output Schema (Success - Diff)

```json
{
  "status": "success",
  "operation": "diff",
  "diff": "--- a\n+++ b\n@@ -1,2 +1,2 @@\n hello\n-world\n+WORLD\n",
  "num_changes": 1,
  "text_a_size": 12,
  "text_b_size": 12
}
```

### Output Schema (Success - Apply)

```json
{
  "status": "success",
  "operation": "apply",
  "result": "hello\nWORLD\n",
  "text_size": 12
}
```

### Output Schema (Error)

```json
{
  "status": "error",
  "operation": "apply",
  "reason": "Patch does not apply cleanly: hunk at line 5 failed",
  "text": "..."
}
```

---

## Testing

### Unit Test Examples

```python
def test_diff_simple():
    result = diff_generate("hello", "world")
    assert result["status"] == "success"
    assert "hello" in result["diff"]
    assert "world" in result["diff"]

def test_diff_multiline():
    text_a = "line1\nline2\nline3\n"
    text_b = "line1\nLINE2\nline3\n"
    result = diff_generate(text_a, text_b)
    assert "-line2" in result["diff"]
    assert "+LINE2" in result["diff"]

def test_apply_simple():
    text = "hello\nworld\n"
    patch = "--- a\n+++ b\n@@ -1,2 +1,2 @@\n hello\n-world\n+WORLD\n"
    result = diff_apply(text, patch)
    assert result["status"] == "success"
    assert result["result"] == "hello\nWORLD\n"

def test_apply_add_lines():
    text = "a\nc\n"
    patch = "--- a\n+++ b\n@@ -1,2 +1,3 @@\n a\n+b\n c\n"
    result = diff_apply(text, patch)
    assert result["status"] == "success"
    assert "b" in result["result"]

def test_apply_remove_lines():
    text = "a\nb\nc\n"
    patch = "--- a\n+++ b\n@@ -1,3 +1,2 @@\n a\n-b\n c\n"
    result = diff_apply(text, patch)
    assert result["status"] == "success"
    assert "b" not in result["result"]

def test_apply_bad_patch():
    text = "hello\nworld\n"
    patch = "--- a\n+++ b\n@@ -1,2 +1,2 @@\n goodbye\n-world\n+WORLD\n"
    result = diff_apply(text, patch)
    assert result["status"] == "error"
    assert "does not apply" in result["reason"]

def test_context_lines():
    text_a = "1\n2\n3\n4\n5\n"
    text_b = "1\n2\nX\n4\n5\n"
    
    result1 = diff_generate(text_a, text_b, context_lines=0)
    result2 = diff_generate(text_a, text_b, context_lines=2)
    
    # More context means longer diff
    assert len(result2["diff"]) > len(result1["diff"])

def test_empty_files():
    result = diff_generate("", "hello")
    assert "+hello" in result["diff"]
    
    result = diff_generate("hello", "")
    assert "-hello" in result["diff"]
```

---

## CLI

```bash
# Generate diff
python -m tools.diff_patch generate file_a.txt file_b.txt
# Output: JSON with diff field

python -m tools.diff_patch generate file_a.txt file_b.txt --context 1
# Output: JSON with diff (minimal context)

# Apply patch
python -m tools.diff_patch apply original.txt patch.unified
# Output: JSON with result field

# Pipe usage
diff_generate "a\nb\nc" "a\nB\nc" | diff_apply "a\nb\nc" -
# Output: patched text
```

---

## Non-Goals

- **Three-way merge:** Merging conflicting diffs. Deferred to v2.
- **Binary diffs:** Only text. Binary data returns error.
- **Complex patch formats:** Only unified diff (RFC 3881). No git-format, no context diffs.
- **Performance optimization:** No special handling for huge files (>100MB). Works but may be slow.
- **Reversibility:** Cannot generate reverse patch automatically. Must manually negate +/- lines (tool doesn't do this).

---

## Related Components

- **Math Evaluation** — can use in diff analysis (counting changes)
- **Text Search** — can find lines matching a pattern in diffs
- **Templating** — can generate diff headers/metadata
- **Dream Bucket** — stores diffs as events instead of full snapshots
- **Stage 5 recalibration** — uses diffs for approving/rejecting changes
