"""CLI for tools.episode_annotation_tool.

Subcommands:
  annotate  Mark an episode boundary. JSON to stdout; summary to stderr. Exit 0 ok / 1 error.
  read      Dump the episodes JSONL log. Exit 0.

Stdlib only.
"""
import argparse
import json
import sys

from .core import annotate_episode, read_episodes, DEFAULT_LOG_PATH


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.episode_annotation_tool")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("annotate")
    a.add_argument("--phase", required=True)
    a.add_argument("--summary", required=True)
    a.add_argument("--session-id", default=None)
    a.add_argument("--query-id", default=None)
    a.add_argument("--agent-context", default=None,
                   help="JSON string for agent_context snapshot")
    a.add_argument("--log-path", default=DEFAULT_LOG_PATH)

    r = sub.add_parser("read")
    r.add_argument("--log-path", default=DEFAULT_LOG_PATH)

    args = p.parse_args(argv)
    try:
        if args.cmd == "annotate":
            ctx = None
            if args.agent_context:
                ctx = json.loads(args.agent_context)
            result = annotate_episode(
                args.phase, args.summary,
                session_id=args.session_id, query_id=args.query_id,
                agent_context=ctx, log_path=args.log_path,
            )
        else:
            result = {"episodes": read_episodes(args.log_path), "status": "ok"}
    except (ValueError, OSError) as e:
        sys.stderr.write(f"[error] {e}\n")
        return 2

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") in ("logged", "ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
