# diff_patch

Generate unified diffs (RFC 3881) and apply them back to text. Core to
iterative file editing, Dream Bucket versioning (store diffs, not full
snapshots), and Stage 5 recalibration. `tools.diff_patch`.

## Interface

```python
diff_generate("hello\nworld", "hello\nWORLD")
# {"status":"success","operation":"diff","diff":"--- ...\n+++ ...\n@@ -1,2 +1,2 @@\n hello\n-world\n+WORLD\n",...}

diff_apply("hello\nworld", patch)
# {"status":"success","operation":"apply","result":"hello\nWORLD\n","text_size":...}
```

| Function | Purpose |
|----------|---------|
| `diff_generate(text_a, text_b, context_lines=3)` | Unified diff; return result/error dict |
| `diff_apply(text, patch)` | Apply unified diff; return result/error dict |

`diff_generate` uses `difflib.unified_diff`. `diff_apply` parses hunks and
applies with 1-line fuzz tolerance; mismatched context returns
`{"status":"error","reason":"Patch does not apply cleanly:..."}`. Binary
(null-byte) input errors. Errors returned as dicts, never raised.

## CLI

```bash
python -m tools.diff_patch generate a.txt b.txt --context 1
python -m tools.diff_patch apply orig.txt patch.unified
```

JSON to stdout, summary to stderr. Exit 0 = success, 1 = error. Pure stdlib;
same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-diff_patch_v1.md` · **Test:** `TEST-diff_patch_examples.json`
