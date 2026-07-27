from __future__ import annotations

from functools import lru_cache

import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser, Node


@lru_cache(maxsize=1)
def get_parser() -> Parser:
    language = Language(tscpp.language())
    parser = Parser(language)
    return parser


def parse_source(source: str) -> tuple[bytes, Node]:
    source_bytes = source.encode("utf-8")
    tree = get_parser().parse(source_bytes)
    return source_bytes, tree.root_node


def node_text(source_bytes: bytes, node: Node) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8")


def line_number(source: str, byte_offset: int) -> int:
    return source[:byte_offset].count("\n") + 1


def walk(node: Node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        for child in reversed(current.children):
            stack.append(child)


def find_children(node: Node, node_type: str) -> list[Node]:
    return [child for child in node.children if child.type == node_type]


def find_descendants(node: Node, node_type: str) -> list[Node]:
    return [n for n in walk(node) if n.type == node_type]
