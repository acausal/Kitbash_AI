# multispectral_analyzer

Prism tool: fingerprint data through parallel analytical **spectra** (Historical AI batch).
Stdlib-only, stateless, JSON I/O. See `SPEC-multispectral_analyzer_v1.md`.

## What it does (MVP)

Runs a configurable set of text spectra on one piece of data and returns one
multispectral JSON: each spectrum's raw output, a `fingerprint` (SHA256 of the
spectral results + a small numeric `signature`), and `divergence_flags` (simple
threshold comparisons, **flag-only — no action**).

### MVP spectrum set (7 of the spec's 9)

| Spectrum | Tool | Notes |
|----------|------|-------|
| surface | `tokenizer` | spaCy |
| entities | `ner` | spaCy |
| semantics | `svo` | spaCy |
| epistemic | `negation_detector` | spaCy |
| frequency | `frequency_analysis` | stdlib |
| semantic_weight | `tfidf_ranker` | stdlib |
| (deferred) classification | `naive_bayes_classifier` | needs trained model |
| (deferred) markov | `markov_chain` | needs trained model |
| (deferred) anomaly | `anomaly_scorer` | post-collection integration |

JSON / log `data_type` values are **deferred** (spec §9.3) — MVP is text-only and
rejects `json`/`log` with a clear error rather than silently running.

## Library

```python
from tools.multispectral_analyzer import analyze_multispectral

result = analyze_multispectral(
    data="The cat did NOT sit on the mat.",
    data_type="text",
    spectrum_config={"enabled": ["surface","entities","semantics","epistemic","frequency","semantic_weight"], "disabled": []},
    detect_divergence=True,
)
# result["spectral_results"]   -> {spectrum: {tool_id, success, output|error, execution_time_ms}}
# result["fingerprint"]        -> {hash, signature:{entity_density, negation_ratio, entropy, tfidf_mean}}
# result["divergence_flags"]   -> [{divergence_type, spectra_involved, description, severity}]
# result["execution_summary"]  -> {total_time_ms, spectra_attempted, spectra_succeeded, spectra_failed, failures}
```

## CLI

```bash
PYTHONPATH= .venv/Scripts/python.exe -m tools.multispectral_analyzer \
  --data "The cat did NOT sit on the mat." \
  --data-type text \
  --spectrum-config '{"enabled":["surface","entities","semantics","epistemic","frequency","semantic_weight"],"disabled":[]}' \
  --detect-divergence true \
  --output results.json
  # --output-json results.json   (alias for --output)
```

Reads from `--data`, `--input FILE`, or stdin; writes JSON to `--output`/`--output-json`
or stdout. Exit 0 ok, 1 runtime error, 2 usage error.

## MVP deviations from SPEC (locked)

1. **Direct in-memory import, not ToolRegistry.** The spec's `registry.invoke()` path
   assumes a `ToolRegistry` that does not exist yet (deferred to post-1.0). This tool
   imports each spectrum's function directly. **Migration path:** when `ToolRegistry`
   lands, refactor `spectrum_tools.run_spectrum()` to route through `registry.invoke()`
   — a mechanical change. Documented so the divergence is explicit.
2. **7 spectra, not 9.** `classification`/`markov` need trained models (no training data
   in MVP); `anomaly` is deferred to post-collection. All three are absent from
   `SPECTRUM_TOOL_MAP`.
3. **CLI flag: `--output` canonical**, with `--output-json` accepted as an alias.
   The spec wrote `--output-json` only; the project convention keeps `--output`.
4. **Divergence rules restated** (spec §5.2 + MVP §1.3): `semantic_density_mismatch`
   (high entity_density + low tfidf_mean) and `confidence_mismatch` (high tfidf_mean +
   high negation_ratio), plus an optional `entropy_anomaly`. All thresholds are MVP
   guesses (§4.3) — refine post-collection. No interpretation/action is taken.
5. **No per-spectrum timeout enforcement** (Python lacks cross-platform function
   timeouts without `signal`). Specified as post-1.0.

## Environment caveat (IMPORTANT)

Four spectra depend on spaCy + `en_core_web_sm`. In this venv a leaked Hermes
`PYTHONPATH` shadows `pydantic`, so spaCy fails to load (`RuntimeError: spaCy not
installed`). **To run the spaCy-backed spectra for real, invoke the Kitbash venv
python with an empty `PYTHONPATH`:**

```bash
PYTHONPATH= .venv/Scripts/python.exe tools/run_TEST.py
```

Without that prefix, the 4 spaCy spectra **degrade gracefully** (recorded as
`success=False` with the error; the other spectra still run; the tool returns a valid
result with fingerprint). The durable runner's multispectral cases are written for the
`PYTHONPATH=` invocation (all 6 spectra succeed). Graceful degradation itself is a
verified, intended behavior — the tool never crashes on a missing spectrum.

## Testing

`TEST-multispectral_analyzer_examples.json` (4 cases: `text_basic`, `negation_heavy`,
`config_override`, `empty_input`) is owned by `tools/run_TEST.py`. Run with the
`PYTHONPATH=` prefix above → 96 PASS / 0 FAIL.
