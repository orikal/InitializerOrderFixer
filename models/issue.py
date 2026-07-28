from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from models.class_info import ConstructorInfo


class Confidence(str, Enum):
    HIGH = "high"
    LOW = "low"


@dataclass
class Issue:
    class_name: str
    constructor_name: str
    header_path: str
    source_path: str
    line: int
    declared_order: list[str]
    current_order: list[str]
    suggested_order: list[str]
    original_snippet: str
    fixed_snippet: str
    constructor_info: ConstructorInfo
    uninitialized_members: list[str] = field(default_factory=list)
    header_initialized_members: list[str] = field(default_factory=list)
    has_order_mismatch: bool = True
    confidence: Confidence = Confidence.HIGH
    selected: bool = True

    @property
    def current_order_str(self) -> str:
        return "\n".join(self.current_order)

    @property
    def correct_order_str(self) -> str:
        return "\n".join(self.suggested_order)
