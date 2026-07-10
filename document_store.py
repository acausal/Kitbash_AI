#!/usr/bin/env python3
"""
document_store.py — Document Addressing storage layer (SPEC_DOCUMENT_ADDRESSING.md §2.1).

Format-agnostic document store, structurally separate from the cartridge/grain/fact
system. Raw documents are chunked into stable, addressable units and indexed with
SQLite FTS5 (keyword search, zero new dependency). No embeddings (deferred per spec).
No Redis dependency (must work standalone — spec §6 out of scope).

Chunking strategy (Step 1): FORMAT-AGNOSTIC.
  Documents here are not guaranteed Markdown, so we chunk on blank-line paragraph
  boundaries and assign stable line-range keys (doc_id#c<idx>). A heading-aware
  Markdown strategy (Option A) is a FUTURE option, gated on an explicit
  "is this source verifiably Markdown?" check at ingest — NOT a general replacement
  for this. Do not silently swap the two.

Stable addressable IDs:
  chunk_id = f"{doc_id}#c{index}"  (e.g. "whitepaper#c3")
  line range stored as (start_line, end_line) for traceability.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _fts5_available() -> bool:
    """FTS5 must be compiled into this Python's sqlite3. Fail loud if not."""
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except sqlite3.OperationalError:
        return False


class DocumentStoreError(Exception):
    """Loud failure, not silent (spec §5.5 / project discipline)."""


class DocumentStore:
    """
    Format-agnostic chunked document store with FTS5 keyword index.

    Storage: a single SQLite file. Two tables:
      - documents(doc_id, source_type, chunk_count, created_at)
      - chunks(doc_id, chunk_id, idx, start_line, end_line, content)
      - chunks_fts USING fts5(content, doc_id UNINDEXED, chunk_id UNINDEXED)
        (content is the only indexed column; doc_id/chunk_id stored for filtering)
    """

    def __init__(self, db_path: str = "data/document_store/docs.db"):
        if not _fts5_available():
            raise DocumentStoreError(
                "SQLite FTS5 not available in this Python build; document_store "
                "requires FTS5 (ships with standard CPython sqlite3). Refusing to "
                "run keyword search on an unindexed fallback."
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.db_path))
        self._con.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------ schema
    def _init_schema(self) -> None:
        self._con.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                   doc_id      TEXT PRIMARY KEY,
                   source_type TEXT NOT NULL,
                   chunk_count INTEGER NOT NULL,
                   created_at  TEXT NOT NULL
               )"""
        )
        self._con.execute(
            """CREATE TABLE IF NOT EXISTS chunks (
                   doc_id     TEXT NOT NULL,
                   chunk_id   TEXT PRIMARY KEY,
                   idx        INTEGER NOT NULL,
                   start_line INTEGER NOT NULL,
                   end_line   INTEGER NOT NULL,
                   content    TEXT NOT NULL
               )"""
        )
        self._con.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)"
        )
        # FTS5 over content; doc_id/chunk_id carried unindexed for filtered queries.
        self._con.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
            "USING fts5(content, doc_id UNINDEXED, chunk_id UNINDEXED)"
        )
        self._con.commit()

    # ------------------------------------------------------------------ ingest
    @staticmethod
    def _chunk(text: str) -> List[Tuple[int, int, str]]:
        """
        Format-agnostic paragraph chunking: split on blank lines, keep line ranges.
        Returns list of (start_line, end_line, content) for non-empty chunks.
        """
        out: List[Tuple[int, int, str]] = []
        paras = text.split("\n\n")
        line = 1
        for para in paras:
            stripped = para.strip()
            n_lines = para.count("\n") + 1
            if stripped:
                out.append((line, line + n_lines - 1, stripped))
            line += n_lines + 1  # +1 for the blank line separator
        return out

    def ingest(self, doc_id: str, text: str, source_type: str = "text") -> int:
        """
        Ingest a document: chunk it, store chunks, index them in FTS5.
        Re-ingest replaces the prior version (idempotent by doc_id).

        Returns: number of chunks created.
        Raises DocumentStoreError on storage failure (loud, not swallowed).
        """
        try:
            chunks = self._chunk(text)
            if not chunks:
                raise DocumentStoreError(f"document '{doc_id}' produced 0 chunks")

            with self._con:  # atomic transaction
                # remove prior version
                self._remove_doc(doc_id)
                cur = self._con.executemany(
                    "INSERT INTO chunks(doc_id, chunk_id, idx, start_line, end_line, content) "
                    "VALUES (?,?,?,?,?,?)",
                    [
                        (doc_id, f"{doc_id}#c{i}", i, sl, el, content)
                        for i, (sl, el, content) in enumerate(chunks)
                    ],
                )
                import datetime
                self._con.execute(
                    "INSERT INTO documents(doc_id, source_type, chunk_count, created_at) "
                    "VALUES (?,?,?,?)",
                    (doc_id, source_type, len(chunks),
                     datetime.datetime.now(datetime.timezone.utc).isoformat()),
                )
                # FTS5 insert must mirror chunk rows exactly
                self._con.executemany(
                    "INSERT INTO chunks_fts(rowid, content, doc_id, chunk_id) "
                    "SELECT rowid, content, doc_id, chunk_id FROM chunks "
                    "WHERE doc_id = ?",
                    [(doc_id,)],
                )
            return len(chunks)
        except sqlite3.Error as e:
            raise DocumentStoreError(f"ingest failed for '{doc_id}': {e}") from e

    def _remove_doc(self, doc_id: str) -> None:
        self._con.execute(
            "DELETE FROM chunks_fts WHERE doc_id = ?", (doc_id,)
        )
        self._con.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        self._con.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))

    # ------------------------------------------------------------------ read
    def get_chunk(self, doc_id: str, chunk_id: str) -> Optional[str]:
        """Return chunk content, or None if absent."""
        row = self._con.execute(
            "SELECT content FROM chunks WHERE doc_id = ? AND chunk_id = ?",
            (doc_id, chunk_id),
        ).fetchone()
        return row["content"] if row else None

    def list_chunks(self, doc_id: str) -> List[str]:
        """All chunk_ids for a document, in order."""
        return [
            r["chunk_id"]
            for r in self._con.execute(
                "SELECT chunk_id FROM chunks WHERE doc_id = ? ORDER BY idx", (doc_id,)
            )
        ]

    def grep(self, doc_id: str, pattern: str) -> List[str]:
        """Chunk_ids within a document whose content matches the regex `pattern`."""
        import re
        try:
            rx = re.compile(pattern)
        except re.error as e:
            raise DocumentStoreError(f"invalid grep pattern: {e}") from e
        hits = []
        for r in self._con.execute(
            "SELECT chunk_id, content FROM chunks WHERE doc_id = ? ORDER BY idx",
            (doc_id,),
        ):
            if rx.search(r["content"]):
                hits.append(r["chunk_id"])
        return hits

    def search(self, query: str, doc_id: Optional[str] = None) -> List[str]:
        """
        FTS5 keyword search across documents (or one document if doc_id given).
        Returns chunk_ids ranked by bm25 (best first).

        Raises DocumentStoreError on a malformed MATCH query (loud, not swallowed).
        """
        # FTS5 MATCH syntax is picky: bare punctuation/tokens parse as boolean
        # operators and error out ("sub-call" -> "sub AND call" -> "no such column").
        # Tokenize the user query into words, quote each so it's a literal string
        # match, OR them. This gives expected keyword-search semantics.
        fts_query = self._fts5_query(query)
        try:
            if doc_id:
                rows = self._con.execute(
                    "SELECT chunk_id FROM chunks_fts "
                    "WHERE chunks_fts MATCH ? AND doc_id = ? "
                    "ORDER BY bm25(chunks_fts)",
                    (fts_query, doc_id),
                ).fetchall()
            else:
                rows = self._con.execute(
                    "SELECT chunk_id FROM chunks_fts "
                    "WHERE chunks_fts MATCH ? "
                    "ORDER BY bm25(chunks_fts)",
                    (fts_query,),
                ).fetchall()
            return [r["chunk_id"] for r in rows]
        except sqlite3.OperationalError as e:
            raise DocumentStoreError(f"search query invalid: {query!r} ({e})") from e

    @staticmethod
    def _fts5_query(query: str) -> str:
        """Turn a free-text query into a safe FTS5 MATCH string (OR'd quoted terms)."""
        import re
        terms = re.findall(r"\w+", query)
        if not terms:
            raise DocumentStoreError(f"search query has no indexable terms: {query!r}")
        return " OR ".join(f'"{t}"' for t in terms)

    # ------------------------------------------------------------------ meta
    def document_ids(self) -> List[str]:
        return [r["doc_id"] for r in self._con.execute("SELECT doc_id FROM documents")]

    def chunk_count(self, doc_id: str) -> int:
        row = self._con.execute(
            "SELECT chunk_count FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        return row["chunk_count"] if row else 0

    def close(self) -> None:
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
