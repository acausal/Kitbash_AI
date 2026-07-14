"""CLI for tools.trie.

Subcommands: build, search, prefix-search, suggest, negation-search, stats,
serialize, deserialize. Output JSON to stdout; summary to stderr. Exit 0/1/2.
"""
import argparse
import json
import sys

from .core import (
    build_trie, search_trie, prefix_search, suggest_completions, get_trie_stats,
)
from .negation import negation_search
from .serialization import serialize_trie, deserialize_trie


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as e:
        raise RuntimeError(f"input file not found: {path}") from e
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"failed to read {path}: {e}") from e


def _emit(obj):
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.trie", description="Trie/prefix-tree operations")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--vocabulary", required=True)
    b.add_argument("--output", default=None, help="write trie JSON to this path")
    b.add_argument("--case-sensitive", dest="case_sensitive", action="store_true", default=True)
    b.add_argument("--no-case-sensitive", dest="case_sensitive", action="store_false")

    s = sub.add_parser("search")
    s.add_argument("--trie", required=True)
    s.add_argument("--query", required=True)
    s.add_argument("--case-sensitive", dest="case_sensitive", action="store_true", default=True)
    s.add_argument("--no-case-sensitive", dest="case_sensitive", action="store_false")

    ps = sub.add_parser("prefix-search")
    ps.add_argument("--trie", required=True)
    ps.add_argument("--prefix", required=True)
    ps.add_argument("--max-results", type=int, default=None)
    ps.add_argument("--case-sensitive", dest="case_sensitive", action="store_true", default=True)
    ps.add_argument("--no-case-sensitive", dest="case_sensitive", action="store_false")

    su = sub.add_parser("suggest")
    su.add_argument("--trie", required=True)
    su.add_argument("--input", required=True)
    su.add_argument("--max-suggestions", type=int, default=10)
    su.add_argument("--case-sensitive", dest="case_sensitive", action="store_true", default=True)
    su.add_argument("--no-case-sensitive", dest="case_sensitive", action="store_false")

    ns = sub.add_parser("negation-search")
    ns.add_argument("--trie", required=True)
    ns.add_argument("--exclude-patterns", required=True)
    ns.add_argument("--max-results", type=int, default=None)
    ns.add_argument("--case-sensitive", dest="case_sensitive", action="store_true", default=True)
    ns.add_argument("--no-case-sensitive", dest="case_sensitive", action="store_false")

    st = sub.add_parser("stats")
    st.add_argument("--trie", required=True)

    se = sub.add_parser("serialize")
    se.add_argument("--trie", required=True)
    de = sub.add_parser("deserialize")
    de.add_argument("--trie-file", required=True)

    args = p.parse_args(argv)
    try:
        if args.cmd == "build":
            vocab = _load(args.vocabulary)
            result = build_trie(vocab, case_sensitive=args.case_sensitive)
            if args.output:
                try:
                    with open(args.output, "w", encoding="utf-8") as fh:
                        json.dump(result["trie"], fh)
                except OSError as e:
                    raise RuntimeError(f"failed to write {args.output}: {e}") from e
        elif args.cmd == "search":
            result = search_trie(_load(args.trie), args.query, args.case_sensitive)
        elif args.cmd == "prefix-search":
            result = prefix_search(_load(args.trie), args.prefix,
                                   args.case_sensitive, args.max_results)
        elif args.cmd == "suggest":
            result = suggest_completions(_load(args.trie), args.input,
                                         args.case_sensitive, args.max_suggestions)
        elif args.cmd == "negation-search":
            pats = json.loads(args.exclude_patterns)
            result = negation_search(_load(args.trie), pats, args.case_sensitive, args.max_results)
        elif args.cmd == "stats":
            result = get_trie_stats(_load(args.trie))
        elif args.cmd == "serialize":
            result = serialize_trie(_load(args.trie))
        elif args.cmd == "deserialize":
            with open(args.trie_file, encoding="utf-8") as fh:
                raw = fh.read()
            result = deserialize_trie(raw)
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
