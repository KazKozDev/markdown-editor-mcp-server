"""
Document engine - applying operations, transactions, rollbacks.
"""

import uuid
import copy
from typing import Optional, List

from .models import (
    DocumentState,
    Operation,
    OperationType,
    Transaction,
    Journal,
    OperationResult,
)
from .parser import MarkdownParser, find_element_by_path, get_all_paths


class DocumentEngine:
    """Engine for document processing."""

    def __init__(self, content: str = "", journal_path: Optional[str] = None):
        self.parser = MarkdownParser()
        self.journal_path = journal_path

        # Initialize state
        self.state = DocumentState(content=content)
        if content:
            self.state.structure = self.parser.parse(content)

        # Load journal if exists
        if journal_path:
            self.state.journal = Journal.load(journal_path)

    def get_structure(self) -> dict:
        """Returns document structure."""
        if not self.state.structure:
            return {"type": "document", "children": []}
        return self.state.structure.to_dict()

    def get_paths(self) -> List[str]:
        """Returns all paths in document."""
        if not self.state.structure:
            return []
        return get_all_paths(self.state.structure)

    def get_content(self, path: str) -> OperationResult:
        """Gets content by path."""
        if not self.state.structure:
            return OperationResult(
                success=False, message="Document is empty", error_code="empty_document"
            )

        element = find_element_by_path(self.state.structure, path)
        if not element:
            return OperationResult(
                success=False,
                message=f"Path '{path}' not found",
                error_code="path_not_found",
            )

        return OperationResult(
            success=True, message="OK", path=path, old_content=element.content
        )

    def replace(self, path: str, new_content: str) -> OperationResult:
        """Replaces content by path."""
        return self._apply_operation(OperationType.REPLACE, path, new_content)

    def insert_after(
        self, path: str, content: str, element_type: str = "paragraph"
    ) -> OperationResult:
        """Inserts element after specified path."""
        return self._apply_operation(
            OperationType.INSERT_AFTER,
            path,
            content,
            extra={"element_type": element_type},
        )

    def insert_before(
        self, path: str, content: str, element_type: str = "paragraph"
    ) -> OperationResult:
        """Inserts element before specified path."""
        return self._apply_operation(
            OperationType.INSERT_BEFORE,
            path,
            content,
            extra={"element_type": element_type},
        )

    def delete(self, path: str) -> OperationResult:
        """Deletes element by path."""
        return self._apply_operation(OperationType.DELETE, path, None)

    def _apply_operation(
        self,
        op_type: OperationType,
        path: str,
        new_content: Optional[str],
        extra: Optional[dict] = None,
    ) -> OperationResult:
        """Applies operation to document."""

        # Find element
        element = find_element_by_path(self.state.structure, path)
        if not element:
            return OperationResult(
                success=False,
                message=f"Path '{path}' not found. Available paths: {', '.join(self.get_paths()[:10])}...",
                error_code="path_not_found",
            )

        # Save old content
        old_content = element.content

        # Create working copy
        working_content = self.state.content

        try:
            if op_type == OperationType.REPLACE:
                # Replace in raw text
                working_content = (
                    working_content[: element.start_pos]
                    + new_content
                    + working_content[element.end_pos :]
                )

            elif op_type == OperationType.DELETE:
                # Delete from raw text (considering newline)
                end_pos = element.end_pos
                if end_pos < len(working_content) and working_content[end_pos] == "\n":
                    end_pos += 1
                working_content = (
                    working_content[: element.start_pos] + working_content[end_pos:]
                )
                new_content = ""

            elif op_type in (OperationType.INSERT_AFTER, OperationType.INSERT_BEFORE):
                # Form insertion
                elem_type = (
                    extra.get("element_type", "paragraph") if extra else "paragraph"
                )
                insert_text = self._format_element(new_content, elem_type)

                if op_type == OperationType.INSERT_AFTER:
                    insert_pos = element.end_pos
                    # Add newline if needed
                    if (
                        insert_pos < len(working_content)
                        and working_content[insert_pos] != "\n"
                    ):
                        insert_text = "\n" + insert_text
                else:
                    insert_pos = element.start_pos
                    insert_text = insert_text + "\n"

                working_content = (
                    working_content[:insert_pos]
                    + insert_text
                    + working_content[insert_pos:]
                )

            # Validate result
            new_structure = self.parser.parse(working_content)

            # If validation passed - apply
            operation = Operation(
                id=str(uuid.uuid4()),
                type=op_type,
                path=path,
                old_content=old_content,
                new_content=new_content,
            )

            # In transaction - save to draft
            if self.state.active_transaction:
                self.state.active_transaction.add_operation(operation)
            else:
                # Otherwise - straight to journal
                self.state.journal.add(operation)
                if self.journal_path:
                    self.state.journal.save(self.journal_path)

            # Update state
            self.state.content = working_content
            self.state.structure = new_structure
            self.state.increment_version()

            return OperationResult(
                success=True,
                message=f"Operation {op_type.value} completed successfully",
                path=path,
                old_content=old_content,
                new_content=new_content,
            )

        except Exception as e:
            return OperationResult(
                success=False,
                message=f"Error executing operation: {str(e)}",
                error_code="operation_failed",
            )

    def _format_element(self, content: str, elem_type: str) -> str:
        """Formats content according to element type."""
        if elem_type == "heading":
            if not content.startswith("#"):
                content = f"## {content}"
        elif elem_type == "code":
            if not content.startswith("```"):
                content = f"```\n{content}\n```"
        elif elem_type == "list":
            lines = content.split("\n")
            content = "\n".join(
                f"- {line}" if not line.startswith("-") else line for line in lines
            )
        # paragraph - leave as is
        return content

    # === Transactions ===

    def begin_transaction(self) -> OperationResult:
        """Starts transaction."""
        if self.state.active_transaction:
            return OperationResult(
                success=False,
                message="Already have active transaction. Commit or rollback first.",
                error_code="transaction_active",
            )

        self.state.active_transaction = Transaction(id=str(uuid.uuid4()))
        self._transaction_backup = copy.deepcopy(self.state)

        return OperationResult(success=True, message="Transaction started")

    def commit_transaction(self) -> OperationResult:
        """Commits transaction."""
        if not self.state.active_transaction:
            return OperationResult(
                success=False,
                message="No active transaction",
                error_code="no_transaction",
            )

        # Transfer operations to journal
        for op in self.state.active_transaction.operations:
            self.state.journal.add(op)

        if self.journal_path:
            self.state.journal.save(self.journal_path)

        transaction_id = self.state.active_transaction.id
        ops_count = len(self.state.active_transaction.operations)

        self.state.active_transaction = None
        self._transaction_backup = None

        return OperationResult(
            success=True,
            message=f"Transaction {transaction_id} committed ({ops_count} operations)",
        )

    def rollback_transaction(self) -> OperationResult:
        """Rolls back transaction."""
        if not self.state.active_transaction:
            return OperationResult(
                success=False,
                message="No active transaction",
                error_code="no_transaction",
            )

        # Restore from backup
        ops_count = len(self.state.active_transaction.operations)
        self.state = self._transaction_backup
        self._transaction_backup = None

        return OperationResult(
            success=True,
            message=f"Transaction cancelled ({ops_count} operations dropped)",
        )

    # === History and rollback ===

    def undo(self) -> OperationResult:
        """Undoes last operation."""
        if not self.state.journal.entries:
            return OperationResult(
                success=False, message="History is empty", error_code="empty_history"
            )

        last_op = self.state.journal.entries[-1]
        inverse = last_op.inverse()

        # Apply inverse operation
        result = self._apply_operation(inverse.type, inverse.path, inverse.new_content)

        if result.success:
            # Remove last entry from journal
            self.state.journal.entries.pop()
            # And inverse operation too
            self.state.journal.entries.pop()

            if self.journal_path:
                self.state.journal.save(self.journal_path)

        return result

    def get_history(self, limit: int = 10) -> List[dict]:
        """Returns change history."""
        return [op.to_dict() for op in self.state.journal.get_last(limit)]

    def get_content_raw(self) -> str:
        """Returns raw Markdown."""
        return self.state.content

    def load_content(self, content: str):
        """Loads new content."""
        self.state.content = content
        self.state.structure = self.parser.parse(content)
        self.state.version = 0
