# markov_chain

Order-n Markov chain over token sequences (Historical AI batch). Build transition
counts/probabilities, compute entropy, generate deterministic sequences from a
seed. Stateless, deterministic, stdlib-only. See SPEC-markov_chain_v1.md.

## Library

```python
from tools.markov_chain import build_chain, compute_entropy, generate_sequence, next_token_distribution
seqs = [["ai","ml","nlp"],["ai","ml","cv"],["ai","cv"]]
chain = build_chain(seqs, {"order":1})
ent = compute_entropy(chain)
gen = generate_sequence(chain, seed_context=["ai"], length=5, seed=42)
#   gen["generated_sequence"] is reproducible for the same seed/context/length
dist = next_token_distribution(chain, ["ai"])   # {ml: p, cv: p}
```

Entropy: per-context -sum(p*log2 p), averaged (weighted by outgoing count).

## CLI

```bash
echo '{"sequences":[["ai","ml","nlp"],["ai","ml","cv"],["ai","cv"]]}' | python -m tools.markov_chain
python -m tools.markov_chain --entropy --input chain.json
python -m tools.markov_chain --generate --seed-context '["ai"]' --length 5 --seed 42 --input chain.json
```

Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Notes
- Determinism: generation uses random.Random(seed) -> identical for same inputs.
- Unknown context backs off to shorter suffix; stops if no continuation exists.
- `run_id`/`timestamp` differ per call; model + generation are fully deterministic.
