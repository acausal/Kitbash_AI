"""Trie node model for tools.trie (stdlib only).

Internally a trie is a tree of TrieNode; `to_dict()` flattens it to the nested
dict form the SPEC uses for output/serialization (terminal nodes carry the
END marker as a child key).
"""
from dataclasses import dataclass, field
from typing import Dict, Optional


END = "\x00"  # terminal marker (unlikely to collide with real characters)


@dataclass
class TrieNode:
    children: Dict[str, "TrieNode"] = field(default_factory=dict)
    terminal: bool = False

    def insert(self, word: str) -> None:
        node = self
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.terminal = True

    def to_dict(self) -> dict:
        d = {}
        if self.terminal:
            d[END] = True
        for ch, child in self.children.items():
            d[ch] = child.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TrieNode":
        node = cls()
        node.terminal = END in d
        for ch, child in d.items():
            if ch == END:
                continue
            node.children[ch] = cls.from_dict(child)
        return node
