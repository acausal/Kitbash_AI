"""Shared helpers for Historical AI tools (stateless IR/NLP batch utilities).

This is NOT a tool — it has no TEST fixture and is not in run_TEST.OWNED_PACKAGES.
It centralizes the repeated boilerplate the shared contract imposes on every tool:
config normalization, stopword filtering, the standard JSON output envelope, the
argparse CLI skeleton, and JSON error emission. Imported by the 6 Historical AI
tools to keep each one thin and consistent.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence


DEFAULT_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "to", "in",
    "on", "at", "by", "for", "with", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "from", "into", "than",
    "so", "not", "no", "yes", "do", "does", "did", "has", "have", "had", "will",
    "would", "can", "could", "should", "may", "might", "must", "i", "you", "he",
    "she", "we", "they", "them", "his", "her", "their", "our", "your",
})


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def normalize_config(config: Optional[dict]) -> Dict[str, Any]:
    """Apply shared-contract defaults so tool logic gets a complete config."""
    config = dict(config or {})
    norm = {
        "lowercase": bool(config.get("lowercase", True)),
        "remove_stopwords": bool(config.get("remove_stopwords", False)),
        "stopword_list": list(config.get("stopword_list", DEFAULT_STOPWORDS)),
        "min_token_length": int(config.get("min_token_length", 1)),
        "max_token_length": config.get("max_token_length", None),
        "top_k": int(config.get("top_k", 10)),
        "threshold": float(config.get("threshold", 0.0)),
        "verbose": bool(config.get("verbose", False)),
    }
    # merge any tool-specific extras back in (e.g. tfidf_variant, order)
    for k, v in config.items():
        norm.setdefault(k, v)
    return norm


def _filter_tokens(tokens: Sequence[str], cfg: Dict[str, Any]) -> List[str]:
    stop = set(cfg.get("stopword_list", DEFAULT_STOPWORDS))
    lo = cfg.get("lowercase", True)
    mn = int(cfg.get("min_token_length", 1))
    mx = cfg.get("max_token_length", None)
    out = []
    for t in tokens:
        if not isinstance(t, str):
            t = str(t)
        if lo:
            t = t.lower()
        if cfg.get("remove_stopwords") and t in stop:
            continue
        if mx is not None and len(t) > mx:
            continue
        if len(t) >= mn:
            out.append(t)
    return out


def normalize_token_list(tokens: Sequence[str], cfg: Dict[str, Any]) -> List[str]:
    """Apply lowercase/stopwords/min-length to a flat token list (in-place order kept)."""
    return _filter_tokens(tokens, cfg)


def normalize_corpus(corpus: Sequence[dict], cfg: Dict[str, Any]) -> List[dict]:
    """Return corpus with each doc's tokens filtered (id preserved)."""
    out = []
    for doc in corpus:
        toks = _filter_tokens(doc.get("tokens", []), cfg)
        nd = dict(doc)
        nd["tokens"] = toks
        out.append(nd)
    return out


def envelope(tool: str, version: str = "v1") -> Dict[str, Any]:
    return {
        "tool": tool,
        "version": version,
        "run_id": make_run_id(tool),
        "timestamp": now_iso(),
    }


def emit_error(etype: str, msg: str, code: int) -> None:
    sys.stderr.write(json.dumps({
        "error_type": etype, "error_message": msg,
        "error_code": code, "timestamp": now_iso(),
    }) + "\n")


def load_input(path: Optional[str]) -> dict:
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    data = sys.stdin.read()
    if not data.strip():
        raise ValueError("empty input")
    return json.loads(data)


def write_output(result: dict, path: Optional[str]) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text + "\n")


def base_argparse(tool: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=tool)
    p.add_argument("--input", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--verbose", action="store_true")
    return p


def fail(etype: str, msg: str, code: int) -> int:
    emit_error(etype, msg, code)
    return code
