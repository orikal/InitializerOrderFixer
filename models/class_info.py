from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemberInfo:
    name: str
    is_static: bool = False
    line: int = 0
    has_default_initializer: bool = False


@dataclass
class ClassInfo:
    qualified_name: str
    simple_name: str
    header_path: str
    members: list[MemberInfo] = field(default_factory=list)

    @property
    def instance_member_names(self) -> list[str]:
        return [m.name for m in self.members if not m.is_static]


@dataclass
class InitializerEntry:
    member_name: str
    text: str
    start_byte: int
    end_byte: int
    line: int
    is_base_or_unknown: bool = False


@dataclass
class ConstructorInfo:
    qualified_class_name: str
    constructor_name: str
    source_path: str
    line: int
    start_byte: int
    entries: list[InitializerEntry]
    list_start_byte: int
    list_end_byte: int
    full_source: str
