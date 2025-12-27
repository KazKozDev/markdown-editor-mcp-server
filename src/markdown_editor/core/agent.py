"""
Agent for working with documents through LLM.
Connects LLM with DocumentEngine tools.
"""

import json
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

from .engine import DocumentEngine
from .llm_client import LLMClient, Message, build_tools_schema
from ..config.loader import Config


@dataclass
class AgentResponse:
    """Agent response."""

    message: str
    tool_calls: List[dict] = None
    tool_results: List[dict] = None


class DocumentAgent:
    """Agent for document processing."""

    def __init__(self, config: Config, document_path: Optional[str] = None):
        self.config = config
        self.llm = LLMClient(config.llm)

        # Load document if path specified
        initial_content = ""
        if document_path:
            with open(document_path, "r", encoding="utf-8") as f:
                initial_content = f.read()

        self.engine = DocumentEngine(
            content=initial_content, journal_path=config.document.journal_path
        )

        # Message history
        self.messages: List[Message] = []

        # Initialize system prompt
        system_prompt = config.prompts.get(
            "system_prompt", "You are a document editing agent."
        )
        self.messages.append(Message(role="system", content=system_prompt))

        # Tool schema
        tool_descriptions = config.prompts.get("tool_descriptions", {})
        self.tools_schema = build_tools_schema(tool_descriptions)

        # Mapping tool names to methods
        self.tool_handlers: Dict[str, Callable] = {
            "get_structure": self._tool_get_structure,
            "get_content": self._tool_get_content,
            "replace": self._tool_replace,
            "insert_after": self._tool_insert_after,
            "insert_before": self._tool_insert_before,
            "delete": self._tool_delete,
            "begin_transaction": self._tool_begin_transaction,
            "commit_transaction": self._tool_commit_transaction,
            "rollback_transaction": self._tool_rollback_transaction,
            "undo": self._tool_undo,
            "get_history": self._tool_get_history,
        }

    def chat(self, user_message: str) -> AgentResponse:
        """Processes user message in loop until final response."""

        # Add user message
        self.messages.append(Message(role="user", content=user_message))

        all_tool_calls = []
        all_tool_results = []

        # Loop up to 5 iterations to prevent infinite calls
        for _ in range(5):
            # Get response from LLM
            response = self.llm.chat(self.messages, self.tools_schema)

            if not response.tool_calls:
                # If no tools - this is final response
                self.messages.append(response)
                return AgentResponse(
                    message=response.content,
                    tool_calls=all_tool_calls or None,
                    tool_results=all_tool_results or None,
                )

            # If there are tool calls - execute them
            self.messages.append(response)
            all_tool_calls.extend(response.tool_calls)

            current_step_results = []
            for tc in response.tool_calls:
                result = self._execute_tool(tc["name"], tc["arguments"])
                result_item = {
                    "tool": tc["name"],
                    "arguments": tc["arguments"],
                    "result": result,
                }
                all_tool_results.append(result_item)
                current_step_results.append(result_item)

                # Add result to history for next LLM step
                self.messages.append(
                    Message(
                        role="tool",
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tc["id"],
                    )
                )

            # Continue loop - on next iteration LLM will see tool results

        return AgentResponse(
            message="Agent iteration limit exceeded.",
            tool_calls=all_tool_calls,
            tool_results=all_tool_results,
        )

    def _execute_tool(self, name: str, arguments: dict) -> dict:
        """Executes tool."""
        handler = self.tool_handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}

        try:
            # arguments can be JSON string
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            return handler(**arguments)
        except Exception as e:
            return {"error": str(e)}

    # === Tool handlers ===

    def _tool_get_structure(self) -> dict:
        structure = self.engine.get_structure()
        paths = self.engine.get_paths()
        return {"structure": structure, "paths": paths}

    def _tool_get_content(self, path: str) -> dict:
        result = self.engine.get_content(path)
        return result.to_dict()

    def _tool_replace(self, path: str, new_content: str) -> dict:
        result = self.engine.replace(path, new_content)
        return result.to_dict()

    def _tool_insert_after(
        self, path: str, content: str, element_type: str = "paragraph"
    ) -> dict:
        result = self.engine.insert_after(path, content, element_type)
        return result.to_dict()

    def _tool_insert_before(
        self, path: str, content: str, element_type: str = "paragraph"
    ) -> dict:
        result = self.engine.insert_before(path, content, element_type)
        return result.to_dict()

    def _tool_delete(self, path: str) -> dict:
        result = self.engine.delete(path)
        return result.to_dict()

    def _tool_begin_transaction(self) -> dict:
        result = self.engine.begin_transaction()
        return result.to_dict()

    def _tool_commit_transaction(self) -> dict:
        result = self.engine.commit_transaction()
        return result.to_dict()

    def _tool_rollback_transaction(self) -> dict:
        result = self.engine.rollback_transaction()
        return result.to_dict()

    def _tool_undo(self) -> dict:
        result = self.engine.undo()
        return result.to_dict()

    def _tool_get_history(self, limit: int = 10) -> dict:
        history = self.engine.get_history(limit)
        return {"history": history}

    # === Helper methods ===

    def load_document(self, content: str):
        """Loads document."""
        self.engine.load_content(content)

    def load_document_from_file(self, path: str):
        """Loads document from file."""
        with open(path, "r", encoding="utf-8") as f:
            self.engine.load_content(f.read())

    def save_document(self, path: str):
        """Saves document to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.engine.get_content_raw())

    def get_document(self) -> str:
        """Returns current document content."""
        return self.engine.get_content_raw()

    def reset_conversation(self):
        """Resets conversation history."""
        system_prompt = self.config.prompts.get("system_prompt", "")
        self.messages = [Message(role="system", content=system_prompt)]

    def close(self):
        """Closes resources."""
        self.llm.close()
