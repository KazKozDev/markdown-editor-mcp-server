import asyncio
import logging
from typing import Any

from mcp.server import Server, NotificationOptions
from mcp.types import (
    Tool,
    TextContent,
)
import mcp.server.stdio

# Import async wrappers from tool modules
from .tools.edit_tools import (
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

from .tools.file_ops import list_directory, create_directory, create_file, delete_item

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Server("markdown-editor-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    Returns the complete list of tools available in the server.
    Adheres to the 2025 Scaling Standard for MCP.
    """
    return [
        # --- SCALING & DISCOVERY (2025 Standard) ---
        Tool(
            name="search_tools",
            title="Search Tools",
            description="Scalability feature: find the right tool for your complex task among all available tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Description of the operation you want to perform",
                        "examples": [
                            "find paragraphs",
                            "replace text",
                            "move section",
                            "delete element",
                            "list files",
                        ],
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "tools": {
                        "type": "array",
                        "description": "List of relevant tool names",
                        "items": {"type": "string"},
                    }
                },
            },
        ),
        # --- NAVIGATION & STRUCTURE ---
        Tool(
            name="get_document_structure",
            title="Get Document Structure",
            description="Parses the Markdown file and returns a tree of headings and elements. Use this first to navigate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the .md file",
                        "examples": ["/path/to/document.md", "./README.md"],
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum depth of headings to return",
                        "default": 2,
                        "examples": [2, 3, 5],
                    },
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "structure": {
                        "type": "array",
                        "description": "Tree of document elements",
                    }
                },
            },
        ),
        Tool(
            name="search_text",
            title="Search Text in Document",
            description="Performs a semantic search for text strings and returns their structural paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "examples": ["./document.md", "/path/to/file.md"],
                    },
                    "query": {
                        "type": "string",
                        "description": "String to search for",
                        "examples": ["TODO", "urgent", "deadline"],
                    },
                },
                "required": ["file_path", "query"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "description": "List of matching elements with their paths",
                    }
                },
            },
        ),
        Tool(
            name="get_context",
            title="Get Element Context",
            description="Returns the target element along with its immediate neighbors (before and after).",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "examples": ["./document.md"]},
                    "path": {
                        "type": "string",
                        "description": "Path to the element (e.g., 'Intro > paragraph 1')",
                        "examples": ["Introduction > paragraph 2", "Conclusion"],
                    },
                },
                "required": ["file_path", "path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "object", "description": "The target element"},
                    "before": {
                        "type": "object",
                        "description": "Element before target",
                    },
                    "after": {"type": "object", "description": "Element after target"},
                },
            },
        ),
        # --- CONTENT EDITING ---
        Tool(
            name="read_element",
            title="Read Specific Element",
            description="Fetches the full content of a specific block by its path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "examples": ["./document.md"]},
                    "path": {
                        "type": "string",
                        "examples": ["Features > list 1", "Introduction"],
                    },
                },
                "required": ["file_path", "path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "element": {
                        "type": "object",
                        "description": "The requested element",
                    },
                    "content": {"type": "string", "description": "Element content"},
                },
            },
        ),
        Tool(
            name="replace_content",
            title="Replace Block Content",
            description="Overwrites the content of a specific block. Maintains document structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "examples": ["./document.md"]},
                    "path": {
                        "type": "string",
                        "examples": [
                            "Introduction > paragraph 1",
                            "Conclusion",
                            "Features > list 2",
                        ],
                    },
                    "new_content": {
                        "type": "string",
                        "examples": ["Updated paragraph text", "New content here"],
                    },
                },
                "required": ["file_path", "path", "new_content"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {"success": {"type": "boolean"}},
            },
        ),
        Tool(
            name="insert_element",
            title="Insert New Element",
            description="Inserts a new block (heading, paragraph, etc.) relative to an existing one.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "examples": ["./document.md"]},
                    "path": {
                        "type": "string",
                        "description": "Reference path",
                        "examples": ["Introduction", "Features > paragraph 2"],
                    },
                    "element_type": {
                        "type": "string",
                        "enum": [
                            "heading",
                            "paragraph",
                            "list",
                            "code_block",
                            "blockquote",
                        ],
                        "examples": ["paragraph", "heading"],
                    },
                    "content": {
                        "type": "string",
                        "examples": ["New paragraph content", "## New Section"],
                    },
                    "where": {
                        "type": "string",
                        "enum": ["before", "after"],
                        "default": "after",
                        "examples": ["after", "before"],
                    },
                    "heading_level": {
                        "type": "integer",
                        "default": 1,
                        "examples": [1, 2, 3],
                    },
                },
                "required": ["file_path", "path", "element_type", "content"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {"success": {"type": "boolean"}},
            },
        ),
        Tool(
            name="move_element",
            title="Move Structural Block",
            description="Moves an element (and its children) to a new location in the document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "examples": ["./document.md"]},
                    "source_path": {
                        "type": "string",
                        "examples": ["Old Section", "Introduction > paragraph 2"],
                    },
                    "target_path": {
                        "type": "string",
                        "examples": ["Conclusion", "Features"],
                    },
                    "where": {
                        "type": "string",
                        "enum": ["before", "after"],
                        "default": "after",
                        "examples": ["after", "before"],
                    },
                },
                "required": ["file_path", "source_path", "target_path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {"success": {"type": "boolean"}},
            },
        ),
        Tool(
            name="delete_element",
            title="Delete Block",
            description="Removes a block from the document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "examples": ["./document.md"]},
                    "path": {
                        "type": "string",
                        "examples": [
                            "Introduction > paragraph 3",
                            "Old Section",
                            "Deprecated > list 1",
                        ],
                    },
                },
                "required": ["file_path", "path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {"success": {"type": "boolean"}},
            },
        ),
        Tool(
            name="update_metadata",
            title="Update YAML Metadata",
            description="Modifies the document's Frontmatter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "examples": ["./document.md", "./blog/post.md"],
                    },
                    "metadata": {
                        "type": "object",
                        "examples": [
                            {"status": "published", "tags": ["mcp", "ai"]},
                            {"author": "John Doe", "date": "2025-12-27"},
                        ],
                    },
                },
                "required": ["file_path", "metadata"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {"success": {"type": "boolean"}},
            },
        ),
        Tool(
            name="undo",
            title="Undo Last Changes",
            description="Reverts the last N operations on the document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "examples": ["./document.md"]},
                    "count": {"type": "integer", "default": 1, "examples": [1, 2, 5]},
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "reverted_count": {
                        "type": "integer",
                        "description": "Number of operations reverted",
                    },
                },
            },
        ),
        # --- FILE SYSTEM ---
        Tool(
            name="list_directory",
            title="List Directory",
            description="Lists files and folders in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "default": ".",
                        "examples": [".", "./docs", "/path/to/directory"],
                    }
                },
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "List of directory entries",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "is_dir": {"type": "boolean"},
                                "size": {"type": "integer"},
                                "path": {"type": "string"},
                            },
                        },
                    }
                },
            },
        ),
        Tool(
            name="create_file",
            title="Create File",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "examples": ["./new_document.md", "./notes/todo.md"],
                    },
                    "content": {
                        "type": "string",
                        "default": "",
                        "examples": ["# New Document\n\nContent here", ""],
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "path": {"type": "string"},
                    "size": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="create_directory",
            title="Create Directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "examples": ["./new_folder", "./docs/archive"],
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "path": {"type": "string"},
                },
            },
        ),
        Tool(
            name="delete_item",
            title="Delete File/Folder",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "examples": ["./old_file.md", "./temp_folder"],
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "path": {"type": "string"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> Any:
    """Dispatches tool calls to the appropriate backend functions."""
    try:
        # 1. SPECIAL: Search Tools
        if name == "search_tools":
            query = arguments.get("query", "").lower()
            all_tools = await list_tools()
            relevant = [
                t.name
                for t in all_tools
                if query in t.name or (t.description and query in t.description.lower())
            ]
            return {
                "content": [
                    TextContent(
                        type="text", text=f"Relevant tools: {', '.join(relevant)}"
                    )
                ],
                "structuredContent": {"tools": relevant},
                "isError": False,
            }

        # 2. FILE OPS
        if name == "list_directory":
            path = arguments.get("path", ".")
            items = await list_directory(path)
            return {
                "content": [TextContent(type="text", text=str(items))],
                "structuredContent": {"items": items},
                "isError": items is None,
            }

        elif name == "create_file":
            res = await create_file(arguments["path"], arguments.get("content", ""))
            return {
                "content": [TextContent(type="text", text="File created")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "create_directory":
            res = await create_directory(arguments["path"])
            return {
                "content": [TextContent(type="text", text="Directory created")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "delete_item":
            res = await delete_item(arguments["path"])
            return {
                "content": [TextContent(type="text", text="Item deleted")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        # 3. EDIT OPS (require file_path)
        file_path = arguments.get("file_path")
        if not file_path:
            return {
                "content": [TextContent(type="text", text="Missing file_path")],
                "isError": True,
            }

        if name == "get_document_structure":
            res = await get_document_structure(file_path, arguments.get("depth", 2))
            return {
                "content": [TextContent(type="text", text="Structure extracted")],
                "structuredContent": {"structure": res},
                "isError": False,
            }

        elif name == "search_text":
            res = await search_in_document(file_path, arguments["query"])
            return {
                "content": [TextContent(type="text", text=f"Found {len(res)} matches")],
                "structuredContent": {"results": res},
                "isError": False,
            }

        elif name == "get_context":
            res = await get_element_context(file_path, arguments["path"])
            return {
                "content": [TextContent(type="text", text="Context extracted")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "read_element":
            res = await read_element(file_path, arguments["path"])
            return {
                "content": [TextContent(type="text", text="Element read")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "replace_content":
            res = await replace_content(
                file_path, arguments["path"], arguments["new_content"]
            )
            return {
                "content": [TextContent(type="text", text="Content replaced")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "insert_element":
            res = await insert_element(
                file_path,
                arguments["path"],
                arguments["element_type"],
                arguments["content"],
                arguments.get("where", "after"),
                arguments.get("heading_level", 1),
            )
            return {
                "content": [TextContent(type="text", text="Element inserted")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "move_element":
            res = await move_document_element(
                file_path,
                arguments["source_path"],
                arguments["target_path"],
                arguments.get("where", "after"),
            )
            return {
                "content": [TextContent(type="text", text="Element moved")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "delete_element":
            res = await delete_element(file_path, arguments["path"])
            return {
                "content": [TextContent(type="text", text="Element deleted")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "update_metadata":
            res = await update_document_metadata(file_path, arguments["metadata"])
            return {
                "content": [TextContent(type="text", text="Metadata updated")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        elif name == "undo":
            res = await undo_changes(file_path, arguments.get("count", 1))
            return {
                "content": [TextContent(type="text", text="Undo performed")],
                "structuredContent": res,
                "isError": "error" in res,
            }

        return {
            "content": [TextContent(type="text", text=f"Unknown tool: {name}")],
            "isError": True,
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        return {"content": [TextContent(type="text", text=str(e))], "isError": True}


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        # Enable tools/list_changed notification capability
        notification_options = NotificationOptions(tools_changed=True)
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(
                notification_options=notification_options
            ),
        )


def run():
    asyncio.run(main())
