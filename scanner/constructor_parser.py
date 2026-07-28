from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from models.class_info import ConstructorInfo, InitializerEntry
from scanner.cpp_parser import line_number, node_text, parse_source, walk


def _declarator_name(declarator: Node, source_bytes: bytes) -> str | None:
    for node in walk(declarator):
        if node.type == "destructor_name":
            return None
        if node.type == "identifier":
            return node_text(source_bytes, node)
        if node.type == "qualified_identifier":
            parts: list[str] = []
            for child in node.children:
                if child.type in {"identifier", "namespace_identifier", "destructor_name"}:
                    text = node_text(source_bytes, child)
                    if text != "~":
                        parts.append(text.lstrip("~"))
            if parts:
                return parts[-1]
    return None


def _qualified_class_from_declarator(declarator: Node, source_bytes: bytes) -> tuple[str | None, str | None]:
    """Return (qualified_class_name, constructor_simple_name)."""
    for node in walk(declarator):
        if node.type == "qualified_identifier":
            parts: list[str] = []
            for child in node.children:
                if child.type in {"identifier", "namespace_identifier"}:
                    parts.append(node_text(source_bytes, child))
            if len(parts) >= 2:
                ctor_name = parts[-1]
                class_name = parts[-2]
                qualified = "::".join(parts[:-1])
                return qualified, ctor_name
            if len(parts) == 1:
                return parts[0], parts[0]
        if node.type == "identifier":
            name = node_text(source_bytes, node)
            return name, name
    return None, None


def _extract_initializer_entries(
    init_list: Node,
    source: str,
    source_bytes: bytes,
) -> list[InitializerEntry]:
    entries: list[InitializerEntry] = []
    for child in init_list.children:
        if child.type != "field_initializer":
            continue
        member_name = ""
        for sub in child.children:
            if sub.type in {"identifier", "field_identifier"}:
                member_name = node_text(source_bytes, sub)
                break
            if sub.type == "qualified_identifier":
                parts = [
                    node_text(source_bytes, p)
                    for p in sub.children
                    if p.type in {"identifier", "namespace_identifier"}
                ]
                if parts:
                    member_name = parts[-1]
                break
            if sub.type == "template_function":
                # Base class or member initializer with template — treat as unknown member.
                member_name = node_text(source_bytes, sub).split("(")[0].strip()
                break

        text = source_bytes[child.start_byte : child.end_byte].decode("utf-8")
        is_unknown = not member_name or "(" not in text
        entries.append(
            InitializerEntry(
                member_name=member_name,
                text=text,
                start_byte=child.start_byte,
                end_byte=child.end_byte,
                line=line_number(source, child.start_byte),
                is_base_or_unknown=is_unknown,
            )
        )
    return entries


def _is_constructor(
    func_node: Node,
    source_bytes: bytes,
    outer_class: str | None,
) -> tuple[bool, str | None, str | None]:
    declarator = None
    for child in func_node.children:
        if child.type == "function_declarator":
            declarator = child
            break
    if declarator is None:
        return False, None, None

    qualified, ctor_name = _qualified_class_from_declarator(declarator, source_bytes)
    if qualified is None or ctor_name is None:
        simple = _declarator_name(declarator, source_bytes)
        if simple and outer_class:
            return simple == outer_class.split("::")[-1], outer_class, simple
        return False, None, None

    class_part = qualified.rsplit("::", 1)
    if len(class_part) == 2 and class_part[1] == ctor_name:
        return True, qualified, ctor_name
    if qualified == ctor_name:
        class_simple_name = outer_class.split("::")[-1] if outer_class else qualified
        if ctor_name == class_simple_name:
            resolved_class = outer_class if outer_class else qualified
            return True, resolved_class, ctor_name
        return False, None, None
    if outer_class and qualified == outer_class and ctor_name == outer_class.split("::")[-1]:
        return True, outer_class, ctor_name
    return False, None, None


def _parse_function(
    func_node: Node,
    source: str,
    source_bytes: bytes,
    source_path: str,
    outer_class: str | None,
    results: list[ConstructorInfo],
) -> None:
    is_ctor, qualified, ctor_name = _is_constructor(func_node, source_bytes, outer_class)
    if not is_ctor or not qualified:
        return

    init_list = None
    for child in func_node.children:
        if child.type == "field_initializer_list":
            init_list = child
            break

    if init_list is not None:
        entries = _extract_initializer_entries(init_list, source, source_bytes)
        list_start_byte = init_list.start_byte
        list_end_byte = init_list.end_byte
    else:
        entries = []
        list_start_byte = func_node.start_byte
        list_end_byte = func_node.start_byte

    results.append(
        ConstructorInfo(
            qualified_class_name=qualified,
            constructor_name=ctor_name or qualified.split("::")[-1],
            source_path=source_path,
            line=line_number(source, func_node.start_byte),
            start_byte=func_node.start_byte,
            entries=entries,
            list_start_byte=list_start_byte,
            list_end_byte=list_end_byte,
            full_source=source,
        )
    )


def _class_name_from_specifier(spec_node: Node, source_bytes: bytes) -> str | None:
    for child in spec_node.children:
        if child.type == "type_identifier":
            return node_text(source_bytes, child)
    return None


def _traverse(
    node: Node,
    source: str,
    source_bytes: bytes,
    source_path: str,
    namespace_stack: list[str],
    class_stack: list[str],
    results: list[ConstructorInfo],
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
            _traverse(child, source, source_bytes, source_path, namespace_stack, class_stack, results)
        if name:
            namespace_stack.pop()
        return

    if node.type in {"class_specifier", "struct_specifier"}:
        simple = _class_name_from_specifier(node, source_bytes)
        if simple:
            ns = "::".join(namespace_stack)
            qualified = f"{ns}::{simple}" if ns else simple
            class_stack.append(qualified)
            for child in node.children:
                if child.type == "field_declaration_list":
                    for decl in child.children:
                        if decl.type == "function_definition":
                            _parse_function(
                                decl, source, source_bytes, source_path, qualified, results
                            )
                else:
                    _traverse(
                        child,
                        source,
                        source_bytes,
                        source_path,
                        namespace_stack,
                        class_stack,
                        results,
                    )
            class_stack.pop()
        return

    if node.type == "function_definition":
        outer = class_stack[-1] if class_stack else None
        _parse_function(node, source, source_bytes, source_path, outer, results)
        return

    for child in node.children:
        _traverse(child, source, source_bytes, source_path, namespace_stack, class_stack, results)


def _dedupe_constructors(constructors: list[ConstructorInfo]) -> list[ConstructorInfo]:
    seen: set[tuple[str, int, int, int]] = set()
    unique: list[ConstructorInfo] = []
    for ctor in constructors:
        key = (
            ctor.qualified_class_name,
            ctor.line,
            ctor.list_start_byte,
            ctor.list_end_byte,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(ctor)
    return unique


def parse_source_file(path: Path) -> list[ConstructorInfo]:
    source = path.read_text(encoding="utf-8", errors="replace")
    source_bytes, root = parse_source(source)
    results: list[ConstructorInfo] = []
    _traverse(root, source, source_bytes, str(path), [], [], results)
    return _dedupe_constructors(results)
