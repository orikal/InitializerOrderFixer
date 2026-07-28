from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from models.class_info import ClassInfo, MemberInfo
from scanner.cpp_parser import line_number, node_text, parse_source, walk


def _is_static_field(field_node: Node, source_bytes: bytes) -> bool:
    text = node_text(source_bytes, field_node)
    lowered = text.lower()
    if "static" not in lowered:
        return False
    # Ignore 'static' inside comments or string contexts — rough heuristic.
    for child in field_node.children:
        if child.type in {"storage_class_specifier", "storage_class"}:
            spec = node_text(source_bytes, child).lower()
            if "static" in spec:
                return True
        if child.is_named and child.type == "type_qualifier":
            continue
    # Fallback: leading static keyword before declarator.
    for child in field_node.children:
        if child.type == "static":
            return True
    return " static " in f" {lowered} " or lowered.strip().startswith("static ")


def _has_default_initializer(field_node: Node) -> bool:
    for child in field_node.children:
        if child.type in {"=", "initializer_list", "call_expression", "string_literal", "number_literal"}:
            return True
        if child.type == "init_declarator":
            for sub in child.children:
                if sub.type in {"=", "initializer_list", "call_expression"}:
                    return True
    return False


def _extract_member_name(field_node: Node, source_bytes: bytes) -> str | None:
    for node in walk(field_node):
        if node.type == "field_identifier":
            return node_text(source_bytes, node)
        if node.type == "field_declarator":
            for child in node.children:
                if child.type == "identifier":
                    return node_text(source_bytes, child)
                if child.type == "destructor_name":
                    return None
                if child.type == "pointer_declarator":
                    for sub in walk(child):
                        if sub.type == "identifier":
                            return node_text(source_bytes, sub)
                if child.type == "reference_declarator":
                    for sub in walk(child):
                        if sub.type == "identifier":
                            return node_text(source_bytes, sub)
        if node.type == "function_declarator":
            return None
        if node.type == "identifier" and node.parent and node.parent.type == "field_declaration":
            return node_text(source_bytes, node)
    return None


def _class_name_from_specifier(spec_node: Node, source_bytes: bytes) -> str | None:
    for child in spec_node.children:
        if child.type == "type_identifier":
            return node_text(source_bytes, child)
        if child.type == "template_type":
            for sub in child.children:
                if sub.type == "type_identifier":
                    return node_text(source_bytes, sub)
    return None


def _members_from_body(body_node: Node, source: str, source_bytes: bytes) -> list[MemberInfo]:
    members: list[MemberInfo] = []
    for child in body_node.children:
        if child.type != "field_declaration":
            continue
        if _is_static_field(child, source_bytes):
            continue
        name = _extract_member_name(child, source_bytes)
        if not name:
            continue
        members.append(
            MemberInfo(
                name=name,
                is_static=False,
                line=line_number(source, child.start_byte),
                has_default_initializer=_has_default_initializer(child),
            )
        )
    return members


def _parse_class_or_struct(
    node: Node,
    source: str,
    source_bytes: bytes,
    header_path: str,
    namespace_prefix: str,
    results: dict[str, ClassInfo],
) -> None:
    simple_name = _class_name_from_specifier(node, source_bytes)
    if not simple_name:
        return

    qualified = f"{namespace_prefix}{simple_name}" if namespace_prefix else simple_name

    body = None
    for child in node.children:
        if child.type == "field_declaration_list":
            body = child
            break
    if body is None:
        return

    members = _members_from_body(body, source, source_bytes)
    results[qualified] = ClassInfo(
        qualified_name=qualified,
        simple_name=simple_name,
        header_path=header_path,
        members=members,
    )

    # Nested classes share outer namespace prefix.
    nested_prefix = f"{qualified}::"
    for child in walk(body):
        if child.type in {"class_specifier", "struct_specifier"}:
            _parse_class_or_struct(
                child, source, source_bytes, header_path, nested_prefix, results
            )


def _traverse(
    node: Node,
    source: str,
    source_bytes: bytes,
    header_path: str,
    namespace_stack: list[str],
    results: dict[str, ClassInfo],
) -> None:
    if node.type == "namespace_definition":
        name = None
        body = None
        for child in node.children:
            if child.type == "namespace_identifier":
                name = node_text(source_bytes, child)
            elif child.type == "declaration_list":
                body = child
        if name:
            namespace_stack.append(name)
        target = body if body is not None else node
        for child in target.children:
            _traverse(child, source, source_bytes, header_path, namespace_stack, results)
        if name:
            namespace_stack.pop()
        return

    if node.type in {"class_specifier", "struct_specifier"}:
        prefix = "::".join(namespace_stack)
        if prefix:
            prefix = f"{prefix}::"
        _parse_class_or_struct(node, source, source_bytes, header_path, prefix, results)
        return

    for child in node.children:
        _traverse(child, source, source_bytes, header_path, namespace_stack, results)


def parse_header_file(path: Path) -> dict[str, ClassInfo]:
    source = path.read_text(encoding="utf-8", errors="replace")
    source_bytes, root = parse_source(source)
    results: dict[str, ClassInfo] = {}
    _traverse(root, source, source_bytes, str(path), [], results)
    return results


def parse_headers(paths: list[Path]) -> dict[str, ClassInfo]:
    all_classes: dict[str, ClassInfo] = {}
    for path in paths:
        for qualified, info in parse_header_file(path).items():
            if qualified not in all_classes:
                all_classes[qualified] = info
    return all_classes
