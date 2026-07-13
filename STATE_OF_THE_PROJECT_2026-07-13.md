# STATE OF THE PROJECT — 2026-07-13

**Purpose:** resume point after the usage-collection period. Read this first,
then `SOCKET_MAP.md` (canonical health), then `POST_MVP_ROADMAP.md`.
**HEAD at freeze:** `9650c8a`. Run `git log --oneline 2067b54..HEAD` to see
everything this hardening arc added; anything after `9650c8a` happened during
usage mode and postdates this document.

---

## Where you left off, in one paragraph

The July 11–13 hardening arc closed the self-correction loop end-to-end at
the machinery level: violations now carry fact context (F2 schema), the
recalibration service applies **targeted** edge penalties instead of the old
blanket penalty, the trace chain has a single shared contract both writer
and extractor import, the edge-graph build round-trips (sets↔sorted lists),
and all learning-plane decisions consume a bounded signal while records
preserve raw ground truth. The chat plane was green throughout and stayed
untouched. The loop is **dry-fitted, deliberately not powered on**: Stage 5
has never run against live data, by design. You then switched to usage mode
to grow the corpus the loop needs.

## What the hardening arc shipped (commit chain)

- `0978672` — F2 schema: violations carry `context.recent_fact_ids`
- `de07f16` / `d597ce0` — F2 test fixture (disk-based) + targeted edge
  penalty mapping; F2 contract test GREEN
- `5a7ef41` — observer fail-loud emission (report fields + feed routing),
  deterministic fact attribution (`min(fact_ids)`)
- `bd233ed` / `2067b54` — contract suite mamba stubs repaired (real
  `MambaContext`, hostile fields populated); line-198 serializable
  `mamba_context` projection (hidden_state excluded, timestamps ISO); 23/23
- `fbb1478` — e2e harness `Path` import fix; 10/10 on real torch
- `a242b88` — signal readout (read-only): live `mtr_error` to 8.77,
  confidence to −8.6; 3/67 violations F2-targetable (rest pre-schema)
- `0a7bc27` — Task C gated STOP (chain shape mismatch caught before a
  garbage graph was built)
- `ebb8085` / `30b6c6b` / `e3f6b72` — `interfaces/trace_chain.py` single
  source of truth; **pairwise co-occurrence** edges (order-independent,
  canonical `a<b`, ASCII `->` keys); writer + extractor wired; skip
  accounting loud in stage reports
- `8ccf616` — cartridge_index round-trip fix (sets on load, sorted lists on
  save) + two-pass regression test
- `9650c8a` — `signal_transforms.py`: records raw, decisions clamped;
  killed a latent negative-penalty bug (violations could previously
  *reward* edges)

## Deliberately gated — DO NOT un-gate without the trigger

1. **Live Stage 5 / recalibration run.** Gated on the threshold decision
   below. When it does run for the first time: **report-only mode first**
   (log what it would change), eyeball it, then arm.
2. **Dissonance threshold re-pick** (`GATE_THRESHOLD` in
   `signal_transforms.py`, currently the historical 0.5 on clamped signal).
   **Resume trigger:** a body of real, non-synthetic sessions exists.
   Decide from the empirical distribution — DONE WHEN #4 of
   `SPEC_BOUNDED_SIGNAL_CONSUMPTION.md` prints the transformed
   distribution; re-run it on the fattened corpus. Percentile-based gating
   is the documented alternative if a fixed threshold feels wrong.
3. **Cross-query/session edges.** Deferred ticket (stub in
   `sleep_procedural_edge_extractor.py::extract_cross_cartridge_edges`).
   **Resume trigger:** fact_ids ordering deterministic AND corpus has
   multi-query sessions.

## Open tickets (small, non-blocking)

- `grain_ids` 0% populated across all trace records (534/566 missing at
  readout) — traces never carry grain attribution; wiring gap for future
  sleep stages. Needs a small investigation spec.
- 64 pre-schema violations sit in `violations.jsonl` as untargetable
  archive weight — correct per non-destructive archival, no action; noted
  so the 64/3 split doesn't puzzle you.
- Edge-key convention: ASCII `->` is now canonical (contract docstring, F2
  fixtures, extractor). If any stray `→` keys ever appear, something
  regressed.
- llama-server relaunch after reboot is still a manual terminal action
  (launch-script ticket, pre-1.0 hardening).
- BitNet pop-culture hallucination + summarizer redesign: parked, post-1.0.

## Usage-mode habits (what you told yourself to do)

1. **Vary topology, not just volume** — multi-fact questions grow the edge
   graph; single-fact queries produce zero edges no matter how many.
2. **Every few days:** dry `run_stage_1_5()` (safe; never the full
   pipeline — it would reach Stage 5). Watch edge count rise and confirm
   `chains_skipped_bad_shape == 0`; nonzero skips = bring to a design
   session.
3. **Don't peek at the threshold early** — deciding off a thin corpus
   recreates the synthetic-calibration problem.

## Resume sequence when you're back

1. Re-run the signal distribution readout + a dry Stage 1.5 over the
   fattened corpus; paste both into a design session.
2. Make the threshold decision (item 2 above). Small spec follows.
3. First live Stage 5, report-only → review → armed. The loop is then ON.
4. Then the 1.0 stretch: throwaway chat UI (needs your half-page scope),
   launch script, MTR↔Grain bridge fail-loud sweep (last RED-family cell),
   tag 1.0.
5. Post-1.0 eras per `POST_MVP_ROADMAP.md`: memory → learning → expansion.

## Process notes that earned their keep this arc

- Zero-trust verification caught real issues the reports missed twice
  (unsatisfiable F2 test; dropped skip counters + Unicode key fork).
- Check-first gates prevented a garbage graph once (Task C Step 0).
- Standing agent rule adopted: **the spec file handed over is
  authoritative — commit verbatim; divergences are proposals to raise, not
  decisions to make** (added after the co-occurrence→consecutive-pairs
  drift).
- Recurring disease to keep an eye on: *serializable-by-current-luck*
  containers (MambaContext in context, forced datetimes, sets in
  cartridge_index — three organs, one disease). Vaccine: any test crossing
  a persistence boundary crosses it **twice**.
