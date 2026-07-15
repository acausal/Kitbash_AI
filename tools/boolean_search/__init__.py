"""tools.boolean_search — boolean query over a tokenized corpus (see SPEC).

Recursive-descent parser for AND/OR/NOT + parentheses over a document corpus
(or over an inverted index). Stateless, deterministic, stdlib-only.
"""
from .core import search, parse_query, execute_query
from .query_parser import Tokenizer, Parser
from .search_schema import QueryNode

__all__ = ["search", "parse_query", "execute_query",
           "Tokenizer", "Parser", "QueryNode"]
