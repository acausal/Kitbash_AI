"""tools.diff_patch core (stdlib only; difflib for diff, manual hunk apply).

Generate unified diffs (RFC 3881) and apply them back to text. Used for file
editing and Dream Bucket versioning. See SPEC-diff_patch_v1.md.
"""
import difflib
import re
from typing import Dict, List


def _is_binary(text: str) -> bool:
    return "\x00" in text


def _parse_hunks(patch: str) -> List[Dict]:
    """Parse a unified diff into ordered hunks (0-indexed). Each hunk's `ops`
    preserve line order: (' ', ctx), ('-', removed), ('+', added)."""
    hunks: List[Dict] = []
    cur = None
    header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    for line in patch.split("\n"):
        if line.startswith("@@"):
            m = header.match(line)
            if not m:
                continue
            cur = {
                "old_start": int(m.group(1)) - 1,
                "old_count": int(m.group(2)) if m.group(2) else 1,
                "new_start": int(m.group(3)) - 1,
                "new_count": int(m.group(4)) if m.group(4) else 1,
                "ops": [],  # (' ', ctx) | ('-', removed) | ('+', added)
            }
            hunks.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("-"):
            cur["ops"].append(("-", line[1:]))
        elif line.startswith("+"):
            cur["ops"].append(("+", line[1:]))
        elif line.startswith(" "):
            cur["ops"].append((" ", line[1:]))
        # '\' (no newline at eof) and other lines ignored
    return hunks


def diff_generate(text_a: str, text_b: str, context_lines: int = 3) -> Dict:
    """Return a unified diff between two texts. Errors on binary input."""
    if _is_binary(text_a) or _is_binary(text_b):
        return {"status": "error", "operation": "diff",
                "reason": "Binary data not supported; text only"}
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    diff = list(difflib.unified_diff(lines_a, lines_b, lineterm="", n=context_lines))
    diff_text = "\n".join(diff)
    num_changes = sum(1 for ln in diff
                      if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")))
    return {
        "status": "success", "operation": "diff", "diff": diff_text,
        "num_changes": num_changes,
        "text_a_size": len(text_a), "text_b_size": len(text_b),
    }


def _context_matches(lines: List[str], start: int, hunk: Dict) -> bool:
    """Verify context ops align within the full old-block at `lines[start:]`.

    `pos` steps only for non-`+` ops (old-side lines), so context following a
    `+` insertion lands at its correct text position.
    """
    old_block = [t for k, t in hunk["ops"] if k != "+"]
    if start < 0 or start + len(old_block) > len(lines):
        return False
    pos = start
    for kind, text in hunk["ops"]:
        if kind == "+":
            continue
        if lines[pos].rstrip("\n") != text:
            return False
        pos += 1
    return True


def diff_apply(text: str, patch: str) -> Dict:
    """Apply a unified diff to `text`. Returns patched text or error dict."""
    if _is_binary(text) or _is_binary(patch):
        return {"status": "error", "operation": "apply",
                "reason": "Binary data not supported; text only", "text": text}
    try:
        hunks = _parse_hunks(patch)
        lines = text.splitlines(keepends=True)
        offset = 0
        for h in hunks:
            base = h["old_start"] + offset
            # try exact, then ±1 fuzz
            pos = None
            for cand in (base, base - 1, base + 1):
                if _context_matches(lines, cand, h):
                    pos = cand
                    break
            if pos is None:
                return {"status": "error", "operation": "apply",
                        "reason": f"Patch does not apply cleanly: hunk at line {h['old_start'] + 1} failed",
                        "text": text}
            old_block = [t for k, t in h["ops"] if k != "+"]
            new_block = [t for k, t in h["ops"] if k != "-"]
            del lines[pos:pos + len(old_block)]
            for j, nb in enumerate(new_block):
                lines.insert(pos + j, nb + ("\n" if not nb.endswith("\n") else ""))
            offset += len(new_block) - len(old_block)
        result = "".join(lines)
        return {"status": "success", "operation": "apply",
                "result": result, "text_size": len(result)}
    except Exception as e:  # pragma: no cover - defensive
        return {"status": "error", "operation": "apply",
                "reason": f"Patch does not apply cleanly: {e}", "text": text}
