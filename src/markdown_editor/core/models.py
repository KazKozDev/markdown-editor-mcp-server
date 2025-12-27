"""
Data models for document processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum
import json


class ElementType(Enum):
    DOCUMENT = "document"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    CODE = "code"
    BLOCKQUOTE = "blockquote"
    THEMATIC_BREAK = "thematic_break"


class OperationType(Enum):
    REPLACE = "replace"
    INSERT_AFTER = "insert_after"
    INSERT_BEFORE = "insert_before"
    DELETE = "delete"


@dataclass
class Element:
    """Document structure element."""

    type: ElementType
    content: str
    path: str  # "Introduction > paragraph 1"
    start_pos: int  # Position in source text
    end_pos: int
    level: int = 0  # For headings
    children: List["Element"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "content": (
                self.content[:100] + "..." if len(self.content) > 100 else self.content
            ),
            "path": self.path,
            "level": self.level,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class Operation:
    """Operation record in the journal."""

    id: str
    type: OperationType
    path: str
    old_content: Optional[str]
    new_content: Optional[str]
    timestamp: datetime = field(default_factory=datetime.now)
    transaction_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "path": self.path,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "timestamp": self.timestamp.isoformat(),
            "transaction_id": self.transaction_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Operation":
        return cls(
            id=data["id"],
            type=OperationType(data["type"]),
            path=data["path"],
            old_content=data.get("old_content"),
            new_content=data.get("new_content"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            transaction_id=data.get("transaction_id"),
        )

    def inverse(self) -> "Operation":
        """Create inverse operation for rollback."""
        inverse_type = {
            OperationType.REPLACE: OperationType.REPLACE,
            OperationType.INSERT_AFTER: OperationType.DELETE,
            OperationType.INSERT_BEFORE: OperationType.DELETE,
            OperationType.DELETE: OperationType.INSERT_AFTER,  # Simplification
        }
        return Operation(
            id=f"inverse_{self.id}",
            type=inverse_type[self.type],
            path=self.path,
            old_content=self.new_content,
            new_content=self.old_content,
            transaction_id=self.transaction_id,
        )


@dataclass
class Transaction:
    """Group of related operations."""

    id: str
    operations: List[Operation] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    committed: bool = False

    def add_operation(self, op: Operation):
        op.transaction_id = self.id
        self.operations.append(op)


@dataclass
class Journal:
    """Document change journal."""

    entries: List[Operation] = field(default_factory=list)

    def add(self, operation: Operation):
        self.entries.append(operation)

    def get_last(self, n: int = 10) -> List[Operation]:
        return self.entries[-n:]

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [e.to_dict() for e in self.entries], f, ensure_ascii=False, indent=2
            )

    @classmethod
    def load(cls, path: str) -> "Journal":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return cls(entries=[Operation.from_dict(e) for e in data])
        except FileNotFoundError:
            return cls()


@dataclass
class DocumentState:
    """Complete document state."""

    content: str  # Raw Markdown
    structure: Optional[Element] = None  # Structural tree
    journal: Journal = field(default_factory=Journal)
    version: int = 0
    active_transaction: Optional[Transaction] = None

    def increment_version(self):
        self.version += 1


@dataclass
class OperationResult:
    """Operation execution result."""

    success: bool
    message: str
    path: Optional[str] = None
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    error_code: Optional[str] = None

    def to_dict(self) -> dict:
        result = {"success": self.success, "message": self.message}
        if self.path:
            result["path"] = self.path
        if self.error_code:
            result["error_code"] = self.error_code
        return result
