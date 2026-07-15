"""CLI for tools.markov_chain.

Modes: build (default, from sequences), entropy (on a built chain),
generate (on a built chain). Writes JSON to --output or stdout. Exit 0/1/2.
"""
from __future__ import annotations

import argparse
import json
import sys

from tools.historical_common import base_argparse, load_input, write_output, fail, normalize_config
from .core import build_chain, compute_entropy, generate_sequence


def main(argv=None) -> int:
    p = base_argparse("markov_chain")
    p.add_argument("--entropy", action="store_true", help="compute entropy on a built chain")
    p.add_argument("--generate", action="store_true", help="generate from a built chain")
    p.add_argument("--order", type=int, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--length", type=int, default=None)
    p.add_argument("--seed-context", default=None)
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--remove-stopwords", action="store_true")
    args = p.parse_args(argv)

    try:
        data = load_input(args.input)
        cfg = dict(data.get("config") or {})
        if args.order is not None: cfg["order"] = args.order
        if args.lowercase: cfg["lowercase"] = True
        if args.remove_stopwords: cfg["remove_stopwords"] = True
        cfg = normalize_config(cfg)
        if args.entropy or args.generate:
            chain = dict(data.get("chain") or data.get("chain_state") or {})
            if not chain.get("transitions"):
                raise ValueError("entropy/generate require a built 'chain'")
            if args.entropy:
                result = compute_entropy(chain, cfg)
            else:
                length = args.length if args.length is not None else int(cfg.get("length", 10))
                seed = args.seed if args.seed is not None else int(cfg.get("seed", 42))
                sctx = json.loads(args.seed_context) if args.seed_context else data.get("seed_context")
                result = generate_sequence(chain, sctx, length, seed, cfg)
        else:
            seqs = data.get("sequences")
            if not isinstance(seqs, list):
                raise ValueError("missing 'sequences' list")
            result = build_chain(seqs, cfg)
    except ValueError as e:
        return fail("ValueError", str(e), 1)
    except (OSError, json.JSONDecodeError) as e:
        return fail("RuntimeError", str(e), 2)

    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
