"""Recursive-descent parser for boolean queries (stdlib only).

Grammar (precedence: NOT > AND > OR; parentheses group):
    expr   := term (OR term)*
    term   := factor (AND factor)*
    factor := NOT factor | '(' expr ')' | TOKEN
TOKEN = any run of non-space, non-paren, non-operator chars (quoted strings supported).
"""
from __future__ import annotations

import re
from typing import List

from .search_schema import QueryNode


class Tokenizer:
    """Split a query string into tokens: '(', ')', 'AND', 'OR', 'NOT', or a term."""
    _TOKEN_RE = re.compile(r"""\s*(
        \( | \) |
        "([^"]*)" |
        '([^']*)' |
        [^\s()]+   # bare term
    )""", re.VERBOSE)

    def __init__(self, text: str):
        self.toks: List[str] = []
        for m in self._TOKEN_RE.finditer(text):
            raw = m.group(1)
            if raw == "(" or raw == ")":
                self.toks.append(raw)
            elif m.group(2) is not None:
                self.toks.append(m.group(2))          # double-quoted term
            elif m.group(3) is not None:
                self.toks.append(m.group(3))          # single-quoted term
            else:
                up = raw.upper()
                if up in ("AND", "OR", "NOT"):
                    self.toks.append(up)
                else:
                    self.toks.append(raw)             # bare term (case-preserving)
        self.pos = 0

    def peek(self) -> str:
        return self.toks[self.pos] if self.pos < len(self.toks) else ""

    def next(self) -> str:
        t = self.peek()
        self.pos += 1
        return t


class Parser:
    def __init__(self, text: str):
        self.tok = Tokenizer(text)

    def parse(self) -> QueryNode:
        if not self.tok.toks:
            raise ValueError("empty query")
        node = self._expr()
        if self.tok.peek() != "":
            raise ValueError(f"unexpected token '{self.tok.peek()}' at position {self.tok.pos}")
        return node

    def _expr(self) -> QueryNode:
        node = self._term()
        while self.tok.peek() == "OR":
            self.tok.next()
            rhs = self._term()
            node = QueryNode(op="OR", left=node, right=rhs)
        return node

    def _term(self) -> QueryNode:
        node = self._factor()
        while self.tok.peek() == "AND":
            self.tok.next()
            rhs = self._factor()
            node = QueryNode(op="AND", left=node, right=rhs)
        return node

    def _factor(self) -> QueryNode:
        if self.tok.peek() == "NOT":
            self.tok.next()
            return QueryNode(op="NOT", left=self._factor())
        if self.tok.peek() == "(":
            self.tok.next()
            node = self._expr()
            if self.tok.peek() != ")":
                raise ValueError("missing closing parenthesis")
            self.tok.next()
            return node
        t = self.tok.next()
        if t == "":
            raise ValueError("unexpected end of query")
        if t in ("AND", "OR", "NOT", "(", ")"):
            raise ValueError(f"unexpected operator/brace '{t}' in factor position")
        return QueryNode(op="TERM", term=t)
