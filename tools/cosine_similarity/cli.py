"""CLI for tools.cosine_similarity.

Subcommands: compute-pair, compute-matrix, compute-neighbors, compare-sets.
Vectors may be JSON arrays or JSON files (--vectors etc. accept a path).
Output JSON to stdout; summary to stderr. Exit 0/1/2.
"""
import argparse
import json
import sys

from .core import (
    compute_similarity,
    compute_similarity_matrix,
    compute_vector_neighbors,
    compare_vector_sets,
)


def _load(arg, default=None):
    if arg is None:
        return default
    try:
        with open(arg, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as e:
        raise RuntimeError(f"input file not found: {arg}") from e
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"failed to read {arg}: {e}") from e


def _emit(obj):
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _parse_vec(arg):
    """Parse a vector argument: JSON file path, or inline JSON/Python literal."""
    if arg is None:
        return None
    try:
        return _load(arg)
    except RuntimeError:
        pass
    try:
        return json.loads(arg)
    except json.JSONDecodeError:
        raise ValueError(f"cannot parse vector argument: {arg}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.cosine_similarity", description="Cosine similarity math")
    sub = p.add_subparsers(dest="cmd", required=True)

    cp = sub.add_parser("compute-pair")
    cp.add_argument("--vector-a", required=True)
    cp.add_argument("--vector-b", required=True)
    cp.add_argument("--no-normalize", dest="normalize", action="store_false", default=True)

    cm = sub.add_parser("compute-matrix")
    cm.add_argument("--vectors", required=True)
    cm.add_argument("--vector-ids", default=None)
    cm.add_argument("--no-normalize", dest="normalize", action="store_false", default=True)

    cn = sub.add_parser("compute-neighbors")
    cn.add_argument("--query-vector", required=True)
    cn.add_argument("--vectors", required=True)
    cn.add_argument("--vector-ids", default=None)
    cn.add_argument("--top-k", type=int, default=5)

    cs = sub.add_parser("compare-sets")
    cs.add_argument("--vectors-a", required=True)
    cs.add_argument("--vectors-b", required=True)
    cs.add_argument("--ids-a", default=None)
    cs.add_argument("--ids-b", default=None)

    args = p.parse_args(argv)
    try:
        if args.cmd == "compute-pair":
            va = _parse_vec(args.vector_a)
            vb = _parse_vec(args.vector_b)
            result = compute_similarity(va, vb, normalize=args.normalize)
        elif args.cmd == "compute-matrix":
            vecs = _load(args.vectors)
            ids = _load(args.vector_ids) if args.vector_ids else None
            result = compute_similarity_matrix(vecs, ids, normalize=args.normalize)
        elif args.cmd == "compute-neighbors":
            q = _parse_vec(args.query_vector)
            vecs = _load(args.vectors)
            ids = _load(args.vector_ids) if args.vector_ids else None
            result = compute_vector_neighbors(q, vecs, ids, top_k=args.top_k)
        elif args.cmd == "compare-sets":
            a = _load(args.vectors_a)
            b = _load(args.vectors_b)
            ia = _load(args.ids_a) if args.ids_a else None
            ib = _load(args.ids_b) if args.ids_b else None
            result = compare_vector_sets(a, b, ia, ib)
        else:  # pragma: no cover
            p.error(f"unknown command: {args.cmd}")
            return 2
    except ValueError as e:
        sys.stderr.write(f"[ValueError] {e}\n")
        return 1
    except RuntimeError as e:
        sys.stderr.write(f"[RuntimeError] {e}\n")
        return 2
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
