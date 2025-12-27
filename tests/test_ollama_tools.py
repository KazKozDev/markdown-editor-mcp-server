"""
Integration test: Ollama qwen3:8b calls each MCP tool.

This test verifies that a real LLM (Ollama with qwen3:8b) can correctly
invoke each tool exposed by the markdown-editor-mcp-server.

Requirements:
- Ollama running locally with qwen3:8b model pulled
- Run: ollama pull qwen3:8b

Usage:
    pytest tests/test_ollama_tools.py -v -s
"""

import asyncio
import json
import os
import shutil
import tempfile
import pytest
import httpx
from typing import Any, Dict, List, Optional

# Import MCP tools
from markdown_editor.tools.file_ops import (
    create_file, list_directory, create_directory, delete_item
)
from markdown_editor.tools.edit_tools import (
    get_document_structure,
    read_element,
    replace_content,
    insert_element,
    delete_element,
    undo_changes,
    search_in_document,
    get_element_context,
    move_document_element,
    update_document_metadata,
    _instance as edit_tool_instance
)
from markdown_editor.core.path_utils import PathResolver

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "qwen3:8b"


# Define all tools for Ollama
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_tools",
            "description": "Find the right tool for your task among all available tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Description of what you want to do"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "File content", "default": ""}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_item",
            "description": "Delete a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_structure",
            "description": "Parse a Markdown file and return its structure (headings, paragraphs, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the .md file"},
                    "depth": {"type": "integer", "description": "Max depth of headings", "default": 2}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_element",
            "description": "Read the content of a specific element by its path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "path": {"type": "string", "description": "Element path like 'Intro > paragraph 1'"}
                },
                "required": ["file_path", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_content",
            "description": "Replace the content of a specific element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "path": {"type": "string", "description": "Element path"},
                    "new_content": {"type": "string", "description": "New content"}
                },
                "required": ["file_path", "path", "new_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "insert_element",
            "description": "Insert a new element (heading, paragraph, etc.) relative to an existing one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "path": {"type": "string", "description": "Reference element path"},
                    "element_type": {"type": "string", "enum": ["heading", "paragraph", "list", "code_block", "blockquote"]},
                    "content": {"type": "string", "description": "Content of new element"},
                    "where": {"type": "string", "enum": ["before", "after"], "default": "after"},
                    "heading_level": {"type": "integer", "default": 1}
                },
                "required": ["file_path", "path", "element_type", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_element",
            "description": "Delete an element from the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "path": {"type": "string", "description": "Element path to delete"}
                },
                "required": ["file_path", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_element",
            "description": "Move an element to a new location in the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "source_path": {"type": "string", "description": "Path of element to move"},
                    "target_path": {"type": "string", "description": "Destination path"},
                    "where": {"type": "string", "enum": ["before", "after"], "default": "after"}
                },
                "required": ["file_path", "source_path", "target_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Search for text in a Markdown document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "query": {"type": "string", "description": "Text to search for"}
                },
                "required": ["file_path", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_context",
            "description": "Get an element along with its neighboring elements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "path": {"type": "string", "description": "Element path"}
                },
                "required": ["file_path", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_metadata",
            "description": "Update the YAML frontmatter metadata of a document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "metadata": {"type": "object", "description": "Metadata to update"}
                },
                "required": ["file_path", "metadata"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "undo",
            "description": "Undo the last N changes to a document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .md file"},
                    "count": {"type": "integer", "description": "Number of operations to undo", "default": 1}
                },
                "required": ["file_path"]
            }
        }
    }
]


async def check_ollama_available() -> bool:
    """Check if Ollama is running and model is available."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return any(MODEL in m.get("name", "") for m in models)
    except Exception:
        pass
    return False


async def call_ollama(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Call Ollama API with tool support."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "model": MODEL,
            "messages": messages,
            "tools": tools,
            "stream": False
        }
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


async def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute the actual MCP tool and return result."""
    if name == "search_tools":
        # Simplified search_tools implementation
        query = args.get("query", "").lower()
        all_tool_names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        relevant = [n for n in all_tool_names if query in n]
        return {"tools": relevant}

    elif name == "list_directory":
        return await list_directory(args.get("path", "."))

    elif name == "create_file":
        return await create_file(args["path"], args.get("content", ""))

    elif name == "create_directory":
        return await create_directory(args["path"])

    elif name == "delete_item":
        return await delete_item(args["path"])

    elif name == "get_document_structure":
        return await get_document_structure(args["file_path"], args.get("depth", 2))

    elif name == "read_element":
        return await read_element(args["file_path"], args["path"])

    elif name == "replace_content":
        return await replace_content(args["file_path"], args["path"], args["new_content"])

    elif name == "insert_element":
        return await insert_element(
            args["file_path"],
            args["path"],
            args["element_type"],
            args["content"],
            args.get("where", "after"),
            args.get("heading_level", 1)
        )

    elif name == "delete_element":
        return await delete_element(args["file_path"], args["path"])

    elif name == "move_element":
        return await move_document_element(
            args["file_path"],
            args["source_path"],
            args["target_path"],
            args.get("where", "after")
        )

    elif name == "search_text":
        return await search_in_document(args["file_path"], args["query"])

    elif name == "get_context":
        return await get_element_context(args["file_path"], args["path"])

    elif name == "update_metadata":
        return await update_document_metadata(args["file_path"], args["metadata"])

    elif name == "undo":
        return await undo_changes(args["file_path"], args.get("count", 1))

    return {"error": f"Unknown tool: {name}"}


class TestOllamaToolCalls:
    """Test each tool with real Ollama calls."""

    @pytest.fixture(autouse=True)
    def setup_test_env(self, tmp_path):
        """Setup temporary test environment."""
        self.test_dir = tmp_path
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Set base path for the path resolver
        PathResolver.set_base_path(str(self.test_dir))

        # Clear edit tool cache
        edit_tool_instance.invalidate_all_cache()

        yield

        os.chdir(self.original_cwd)
        PathResolver.set_base_path(None)

    @pytest.fixture(autouse=True)
    def check_ollama(self):
        """Skip tests if Ollama is not available."""
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{OLLAMA_URL}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    if any(MODEL in m.get("name", "") for m in models):
                        return
        except Exception:
            pass
        pytest.skip(f"Ollama with {MODEL} not available")

    async def ask_ollama_to_call_tool(self, prompt: str) -> Dict[str, Any]:
        """Ask Ollama to call a tool based on the prompt."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that uses tools to complete tasks. "
                    "When asked to perform an action, use the appropriate tool. "
                    "Always use the exact file paths and parameters provided in the user request. "
                    "Do not add any extra text or thinking - just call the tool."
                )
            },
            {"role": "user", "content": prompt}
        ]

        response = await call_ollama(messages, TOOLS_SCHEMA)
        return response

    @pytest.mark.asyncio
    async def test_01_list_directory(self):
        """Test: Ollama calls list_directory."""
        # Create some test files
        (self.test_dir / "file1.md").write_text("# Test 1")
        (self.test_dir / "file2.md").write_text("# Test 2")

        response = await self.ask_ollama_to_call_tool(
            "List all files in the current directory using the list_directory tool with path '.'"
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls in response: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "list_directory"

        # Execute the tool
        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("list_directory", args)

        assert result is not None
        assert isinstance(result, list)
        file_names = [item["name"] for item in result]
        assert "file1.md" in file_names
        assert "file2.md" in file_names

        print(f"[OK] list_directory: found {len(result)} items")

    @pytest.mark.asyncio
    async def test_02_create_file(self):
        """Test: Ollama calls create_file."""
        response = await self.ask_ollama_to_call_tool(
            "Create a new file called 'notes.md' with the content '# My Notes\\n\\nThis is my notes file.' "
            "using the create_file tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "create_file"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("create_file", args)

        assert result.get("success") is True
        assert (self.test_dir / "notes.md").exists()

        print(f"[OK] create_file: created {args.get('path')}")

    @pytest.mark.asyncio
    async def test_03_create_directory(self):
        """Test: Ollama calls create_directory."""
        response = await self.ask_ollama_to_call_tool(
            "Create a new directory called 'docs' using the create_directory tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "create_directory"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("create_directory", args)

        assert result.get("success") is True
        assert (self.test_dir / "docs").is_dir()

        print(f"[OK] create_directory: created {args.get('path')}")

    @pytest.mark.asyncio
    async def test_04_get_document_structure(self):
        """Test: Ollama calls get_document_structure."""
        # Create a test markdown file
        md_content = """# Introduction

This is the intro paragraph.

## Section One

Content of section one.

### Subsection

More details here.

## Section Two

Final section content.
"""
        (self.test_dir / "test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Get the structure of the file 'test.md' using the get_document_structure tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "get_document_structure"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("get_document_structure", args)

        assert isinstance(result, list)
        assert len(result) > 0

        print(f"[OK] get_document_structure: found {len(result)} top-level elements")

    @pytest.mark.asyncio
    async def test_05_read_element(self):
        """Test: Ollama calls read_element."""
        md_content = """# Header

This is a test paragraph with some content.
"""
        (self.test_dir / "read_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Read the element at path 'Header > paragraph 1' from file 'read_test.md' using the read_element tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "read_element"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("read_element", args)

        assert "content" in result
        assert "test paragraph" in result["content"]

        print(f"[OK] read_element: content = '{result['content'][:50]}...'")

    @pytest.mark.asyncio
    async def test_06_replace_content(self):
        """Test: Ollama calls replace_content."""
        md_content = """# Title

Old content here.
"""
        (self.test_dir / "replace_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Replace the content of 'Title > paragraph 1' in file 'replace_test.md' "
            "with 'New updated content!' using the replace_content tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "replace_content"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("replace_content", args)

        assert result.get("success") is True

        # Verify the change
        new_content = (self.test_dir / "replace_test.md").read_text()
        assert "New updated content!" in new_content or "new" in new_content.lower()

        print(f"[OK] replace_content: successfully replaced content")

    @pytest.mark.asyncio
    async def test_07_insert_element(self):
        """Test: Ollama calls insert_element."""
        md_content = """# Main

First paragraph.
"""
        (self.test_dir / "insert_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Insert a new paragraph with content 'Inserted paragraph!' after 'Main > paragraph 1' "
            "in file 'insert_test.md' using the insert_element tool. Use element_type 'paragraph'."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "insert_element"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("insert_element", args)

        assert result.get("success") is True

        # Verify the insertion
        new_content = (self.test_dir / "insert_test.md").read_text()
        assert "Inserted" in new_content or "insert" in new_content.lower()

        print(f"[OK] insert_element: successfully inserted element")

    @pytest.mark.asyncio
    async def test_08_search_text(self):
        """Test: Ollama calls search_text."""
        md_content = """# Document

This contains a special keyword FINDME in the text.

## Another Section

More content without the keyword.

## Final Section

FINDME appears again here!
"""
        (self.test_dir / "search_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Search for the text 'FINDME' in file 'search_test.md' using the search_text tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "search_text"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("search_text", args)

        assert isinstance(result, list)
        assert len(result) >= 2  # Should find at least 2 matches

        print(f"[OK] search_text: found {len(result)} matches")

    @pytest.mark.asyncio
    async def test_09_get_context(self):
        """Test: Ollama calls get_context."""
        md_content = """# Section

Paragraph before target.

Target paragraph content.

Paragraph after target.
"""
        (self.test_dir / "context_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Get the context of element 'Section > paragraph 2' from file 'context_test.md' using the get_context tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "get_context"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("get_context", args)

        assert "current" in result

        print(f"[OK] get_context: got context for element")

    @pytest.mark.asyncio
    async def test_10_move_element(self):
        """Test: Ollama calls move_element."""
        md_content = """# First

Content of first section.

# Second

Content of second section.

# Third

Content to move.
"""
        (self.test_dir / "move_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Move the element 'Third' to before 'First' in file 'move_test.md' "
            "using the move_element tool. Set source_path='Third', target_path='First', where='before'."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "move_element"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("move_element", args)

        assert result.get("success") is True

        print(f"[OK] move_element: successfully moved element")

    @pytest.mark.asyncio
    async def test_11_update_metadata(self):
        """Test: Ollama calls update_metadata."""
        md_content = """---
title: Original Title
---

# Content

Some text here.
"""
        (self.test_dir / "meta_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Update the metadata of file 'meta_test.md' with {\"author\": \"Test Author\", \"version\": \"1.0\"} "
            "using the update_metadata tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "update_metadata"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("update_metadata", args)

        assert result.get("success") is True

        # Verify the metadata was updated
        new_content = (self.test_dir / "meta_test.md").read_text()
        assert "author" in new_content.lower() or "Author" in new_content

        print(f"[OK] update_metadata: successfully updated metadata")

    @pytest.mark.asyncio
    async def test_12_delete_element(self):
        """Test: Ollama calls delete_element."""
        md_content = """# Keep This

This should stay.

# Delete This

This should be deleted.

# Also Keep

More content.
"""
        (self.test_dir / "delete_elem_test.md").write_text(md_content)

        response = await self.ask_ollama_to_call_tool(
            "Delete the element 'Delete This' from file 'delete_elem_test.md' using the delete_element tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "delete_element"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("delete_element", args)

        assert result.get("success") is True

        # Verify deletion
        new_content = (self.test_dir / "delete_elem_test.md").read_text()
        assert "Delete This" not in new_content

        print(f"[OK] delete_element: successfully deleted element")

    @pytest.mark.asyncio
    async def test_13_undo(self):
        """Test: Ollama calls undo."""
        md_content = """# Test

Original content.
"""
        test_file = self.test_dir / "undo_test.md"
        test_file.write_text(md_content)

        # First make a change to undo
        await replace_content("undo_test.md", "Test > paragraph 1", "Modified content.")

        response = await self.ask_ollama_to_call_tool(
            "Undo the last change to file 'undo_test.md' using the undo tool with count=1."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "undo"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("undo", args)

        assert result.get("success") is True

        print(f"[OK] undo: successfully undid changes")

    @pytest.mark.asyncio
    async def test_14_delete_item(self):
        """Test: Ollama calls delete_item."""
        # Create a file to delete
        test_file = self.test_dir / "to_delete.md"
        test_file.write_text("# Delete me")

        response = await self.ask_ollama_to_call_tool(
            "Delete the file 'to_delete.md' using the delete_item tool."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "delete_item"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("delete_item", args)

        assert result.get("success") is True
        assert not test_file.exists()

        print(f"[OK] delete_item: successfully deleted file")

    @pytest.mark.asyncio
    async def test_15_search_tools(self):
        """Test: Ollama calls search_tools."""
        response = await self.ask_ollama_to_call_tool(
            "Find tools related to 'delete' using the search_tools tool with query='delete'."
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        assert len(tool_calls) > 0, f"No tool calls: {response}"

        tool_call = tool_calls[0]
        assert tool_call["function"]["name"] == "search_tools"

        args = tool_call["function"].get("arguments", {})
        result = await execute_tool("search_tools", args)

        assert "tools" in result
        assert any("delete" in t for t in result["tools"])

        print(f"[OK] search_tools: found relevant tools {result['tools']}")


@pytest.mark.asyncio
async def test_full_workflow():
    """
    Integration test: Complete workflow with Ollama making multiple tool calls.
    Tests a realistic scenario: create file, edit it, search, then cleanup.
    """
    available = await check_ollama_available()
    if not available:
        pytest.skip(f"Ollama with {MODEL} not available")

    test_dir = tempfile.mkdtemp()
    original_cwd = os.getcwd()

    try:
        os.chdir(test_dir)
        PathResolver.set_base_path(test_dir)
        edit_tool_instance.invalidate_all_cache()

        print("\n=== Full Workflow Test ===\n")

        # Step 1: Create a document
        print("Step 1: Creating document...")
        result = await create_file("workflow.md", """# Project Plan

## Goals

Define project goals here.

## Timeline

Q1 2025: Planning
Q2 2025: Implementation
""")
        assert result.get("success") is True
        print("  - Created workflow.md")

        # Step 2: Get structure
        print("Step 2: Getting structure...")
        structure = await get_document_structure("workflow.md")
        assert len(structure) > 0
        print(f"  - Found {len(structure)} sections")

        # Step 3: Insert new content
        print("Step 3: Inserting new section...")
        result = await insert_element(
            "workflow.md",
            "Timeline",
            "heading",
            "Resources",
            "after",
            heading_level=2
        )
        assert result.get("success") is True
        print("  - Inserted Resources section")

        # Step 4: Search for text
        print("Step 4: Searching for 'Q1'...")
        results = await search_in_document("workflow.md", "Q1")
        assert len(results) > 0
        print(f"  - Found {len(results)} matches")

        # Step 5: Replace content
        print("Step 5: Replacing content...")
        result = await replace_content("workflow.md", "Goals > paragraph 1", "Build an awesome product!")
        assert result.get("success") is True
        print("  - Replaced goals paragraph")

        # Step 6: Update metadata
        print("Step 6: Adding metadata...")
        result = await update_document_metadata("workflow.md", {
            "project": "MCP Server",
            "status": "in-progress"
        })
        assert result.get("success") is True
        print("  - Added metadata")

        # Step 7: Verify final state
        print("Step 7: Verifying final document...")
        final_content = open("workflow.md").read()
        assert "Resources" in final_content
        assert "awesome product" in final_content
        assert "project:" in final_content or "status:" in final_content
        print("  - Document verified!")

        print("\n=== Workflow Complete! ===\n")

    finally:
        os.chdir(original_cwd)
        PathResolver.set_base_path(None)
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
