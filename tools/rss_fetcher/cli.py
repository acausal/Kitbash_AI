"""CLI for tools.rss_fetcher.

Subcommands/flags:
  --url URL                fetch a single feed
  --urls U1,U2,...         fetch multiple (comma-separated)
  --urls-file PATH         fetch URLs listed one-per-line
  --output PATH            write run-result JSON (default: stdout)
  --audit PATH             append audit JSONL
  --timeout N              (1..120, default 30)
  --delay S                sleep between fetches (default 0.5)
  --user-agent UA          (default Kitbash-RSS-Fetcher/1.0)
  --proxy-config PATH      proxy ONLY from this file (never env)
JSON to stdout (or --output). Exit 0 success, 1 ValueError, 2 I/O error.
"""
import argparse
import json
import sys

from .core import fetch_feeds, fetch_single_feed, write_output, write_audit
from .network import load_proxy, DEFAULT_UA


def _collect_urls(args) -> list:
    urls = []
    if args.url:
        urls.append(args.url)
    if args.urls:
        urls.extend(u.strip() for u in args.urls.split(",") if u.strip())
    if args.urls_file:
        with open(args.urls_file, encoding="utf-8") as f:
            urls.extend(line.strip() for line in f if line.strip())
    return urls


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="tools.rss_fetcher")
    p.add_argument("--url")
    p.add_argument("--urls")
    p.add_argument("--urls-file")
    p.add_argument("--output")
    p.add_argument("--audit")
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--user-agent", default=DEFAULT_UA)
    p.add_argument("--proxy-config", default=None)
    args = p.parse_args(argv)
    try:
        urls = _collect_urls(args)
        if not urls:
            sys.stderr.write("[error] no feed URLs provided (use --url/--urls/--urls-file)\n")
            return 1
        proxy = load_proxy(args.proxy_config) if args.proxy_config else {}
        if len(urls) == 1:
            result = fetch_single_feed(urls[0], args.timeout, args.user_agent, proxy)
        else:
            result = fetch_feeds(urls, args.timeout, args.delay, args.user_agent, proxy)
        if args.output:
            write_output(result, args.output)
        else:
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
        if args.audit:
            write_audit(result, args.audit)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 2
    return 0 if result.get("feeds_fetched", 0) >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
