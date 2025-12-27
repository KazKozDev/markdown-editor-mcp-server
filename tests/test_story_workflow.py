import os
import pytest
import httpx
from typing import Any, Dict, List

# Import MCP tools
from markdown_editor.tools.file_ops import create_file, list_directory, delete_item
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
)
from markdown_editor.core.path_utils import PathResolver

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "qwen3:8b"

# Define tools schema (same as before)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_tools",
            "description": "Find the right tool for your task.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_item",
            "description": "Delete file/dir.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_structure",
            "description": "Get MD structure.",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_element",
            "description": "Read element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["file_path", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_content",
            "description": "Replace content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "path": {"type": "string"},
                    "new_content": {"type": "string"},
                },
                "required": ["file_path", "path", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert_element",
            "description": "Insert element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "path": {"type": "string"},
                    "element_type": {"type": "string"},
                    "content": {"type": "string"},
                    "where": {"type": "string"},
                    "heading_level": {"type": "integer"},
                },
                "required": ["file_path", "path", "element_type", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_element",
            "description": "Delete element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["file_path", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_element",
            "description": "Move element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "source_path": {"type": "string"},
                    "target_path": {"type": "string"},
                    "where": {"type": "string"},
                },
                "required": ["file_path", "source_path", "target_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Search text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["file_path", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_context",
            "description": "Get context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["file_path", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_metadata",
            "description": "Update metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["file_path", "metadata"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "undo",
            "description": "Undo changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["file_path"],
            },
        },
    },
]


async def call_ollama(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Call Ollama API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "model": MODEL,
            "messages": messages,
            "tools": TOOLS_SCHEMA,
            "stream": False,
        }
        try:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Ollama call failed: {e}")
            return {{}}


async def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute tool wrapper."""
    print(f"   [Tool Exec] {name} args={args}")

    if name == "list_directory":
        return await list_directory(args.get("path", "."))
    if name == "create_file":
        return await create_file(args["path"], args.get("content", ""))
    if name == "delete_item":
        return await delete_item(args["path"])
    if name == "get_document_structure":
        return await get_document_structure(args["file_path"])
    if name == "read_element":
        return await read_element(args["file_path"], args["path"])
    if name == "replace_content":
        return await replace_content(
            args["file_path"], args["path"], args["new_content"]
        )
    if name == "insert_element":
        return await insert_element(
            args["file_path"],
            args["path"],
            args["element_type"],
            args["content"],
            args.get("where", "after"),
            args.get("heading_level", 1),
        )
    if name == "delete_element":
        return await delete_element(args["file_path"], args["path"])
    if name == "move_element":
        return await move_document_element(
            args["file_path"],
            args["source_path"],
            args["target_path"],
            args.get("where", "after"),
        )
    if name == "search_text":
        return await search_in_document(args["file_path"], args["query"])
    if name == "get_context":
        return await get_element_context(args["file_path"], args["path"])
    if name == "update_metadata":
        return await update_document_metadata(args["file_path"], args["metadata"])
    if name == "undo":
        return await undo_changes(args["file_path"], args.get("count", 1))

    return {"error": f"Unknown tool: {name}"}


@pytest.mark.asyncio
async def test_story_workflow_on_testtesat():
    """
    Runs a full story editing workflow on 'testtesat.md' using Ollama.
    """
    # 1. Setup
    print("\n=== STARTING OLLAMA STORY WORKFLOW ===\n")

    # Check Ollama availability
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code != 200:
                pytest.skip("Ollama not available")
    except Exception:
        pytest.skip("Ollama not available")

    # Use current directory
    cwd = os.getcwd()
    PathResolver.set_base_path(cwd)
    filename = "testtesat.md"

    if not os.path.exists(filename):
        pytest.fail(f"{filename} not found!")

    history = [
        {
            "role": "system",
            "content": "You are an editor. Use the provided tools to edit the markdown file exactly as requested. Do not output conversational text, just use tools.",
        }
    ]

    async def run_step(prompt):
        print(f"\n>>> USER: {prompt}")
        history.append({"role": "user", "content": prompt})

        resp = await call_ollama(history)
        msg = resp.get("message", {})
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            print(f"!!! NO TOOL CALLS. Response: {msg.get('content')}")
            return None

        for tool_call in tool_calls:
            fname = tool_call["function"]["name"]
            fargs = tool_call["function"]["arguments"]

            # Execute
            result = await execute_tool(fname, fargs)
            print(f"   [Result] {str(result)[:100]}...")

            # Add to history
            history.append(msg)  # Add assistant's tool call message
            history.append({"role": "tool", "content": str(result), "name": fname})
            return result  # Return first result for assertions

    # --- Workflow Steps ---

    # 1. List directory to confirm file exists
    res = await run_step(
        "Check if 'testtesat.md' exists in current directory using list_directory."
    )
    assert any(f["name"] == filename for f in res)

    # 2. Get structure
    res = await run_step(f"Get the structure of '{filename}'.")
    assert len(res) > 0

    # 3. Read specific element
    # Path depends on structure. Let's assume the known structure from previous turn.
    # "Хроники Забытого Королевства > Глава 2: Находка > paragraph 2"
    target_path = "Хроники Забытого Королевства > Глава 2: Находка > paragraph 2"
    res = await run_step(f"Read the content of '{target_path}' in '{filename}'.")
    assert "ржавый" in res.get("content", "")

    # 4. Search text
    res = await run_step(f"Search for 'Артур' in '{filename}'.")
    assert len(res) >= 2

    # 5. Get context
    res = await run_step(f"Get context for '{target_path}' in '{filename}'.")
    assert "current" in res

    # 6. Replace content
    new_text = "Он сиял магическим светом."
    res = await run_step(
        f"Change content of '{target_path}' in '{filename}' to '{new_text}'."
    )
    assert res.get("success") is True

    # 7. Insert new chapter
    res = await run_step(
        f"Add a new heading 'Глава 3: Путь' after 'Хроники Забытого Королевства > Глава 2: Находка' in '{filename}'."
    )
    assert res.get("success") is True

    # 8. Update metadata
    res = await run_step(f"Set author to 'Merlin' in metadata for '{filename}'.")
    assert res.get("success") is True

    # 9. Create a copy (File Ops)
    res = await run_step(
        "Create a file 'copy_test.md' with content 'Backup' using create_file."
    )
    assert res.get("success") is True

    # 10. Delete the copy
    res = await run_step("Delete the file 'copy_test.md'.")
    assert res.get("success") is True

    # 11. Undo last change (metadata update or delete? Undo works on document edit, not file ops usually)
    # The last DOCUMENT edit was Update Metadata.
    res = await run_step(f"Undo the last change to '{filename}'.")
    assert res.get("success") is True

    print("\n=== WORKFLOW COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
