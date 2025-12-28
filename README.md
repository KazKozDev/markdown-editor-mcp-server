# Markdown Editor MCP Server

[![Tests](https://github.com/KazKozDev/markdown-editor-mcp-server/actions/workflows/tests.yml/badge.svg)](https://github.com/KazKozDev/markdown-editor-mcp-server/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/markdown-editor-mcp-server)](https://pypi.org/project/markdown-editor-mcp-server/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP 2025](https://img.shields.io/badge/MCP-2025%20Standard-green.svg)](https://modelcontextprotocol.io)

MCP server providing tools for **structured, semantic editing** of Markdown files. Unlike standard text editors, this server understands the logical structure of your documents.

**Fully compliant with MCP 2025 Standard** - includes Tool Search, Examples, Output Schemas, and Dynamic Capabilities.

## Installation

### From PyPI (recommended)

```bash
pip install markdown-editor-mcp-server
```

### From source

```bash
git clone https://github.com/KazKozDev/markdown-editor-mcp-server.git
cd markdown-editor-mcp-server
pip install -e .
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "markdown-editor": {
      "command": "markdown-editor-mcp-server"
    }
  }
}
```

## Available Tools

### Discovery & Scaling

<details>
<summary><b>search_tools</b> - Find the right tool</summary>

**Why LLMs need this:** With 15 tools available, finding the right one can be challenging. This meta-tool helps discover which tool to use for a specific task.

**What it does:** Searches through all available tools and returns the most relevant ones based on your query.

**Parameters:**
- `query` (required): Description of what you want to do

**Example:**
```json
{"query": "replace text"}
```
</details>

### Semantic Editing

<details>
<summary><b>get_document_structure</b> - Get document tree</summary>

**Why LLMs need this:** Large Markdown files are hard to navigate. This tool converts the file into a structural tree, allowing the LLM to understand the hierarchy of headings, paragraphs, and lists.

**What it does:** Parses the Markdown file and returns a JSON tree of all elements with their semantic paths.

**Parameters:**
- `file_path` (required): Path to the .md file
- `depth`: Max depth for the tree (default: 2)

**Example:**
```json
{"file_path": "docs/report.md", "depth": 3}
```
</details>

<details>
<summary><b>search_text</b> - Semantic search and navigation</summary>

**Why LLMs need this:** Instead of scrolling through an entire file, the LLM can search for specific keywords and get exact semantic paths (e.g., `Project > Deadlines > paragraph 2`).

**What it does:** Searches the document for text and returns paths to the containing elements.

**Parameters:**
- `file_path` (required): Path to the file
- `query` (required): Text to search for

**Example:**
```json
{"file_path": "todo.md", "query": "urgent"}
```
</details>

<details>
<summary><b>read_element</b> - Read specific element</summary>

**Why LLMs need this:** Before editing an element, you often need to see its full content. This tool fetches the complete content of a specific block.

**What it does:** Returns the full content of an element identified by its path.

**Parameters:**
- `file_path` (required): Path to the file
- `path` (required): Semantic path to the element

**Example:**
```json
{"file_path": "notes.md", "path": "Features > list 1"}
```
</details>

<details>
<summary><b>replace_content</b> - Precise content replacement</summary>

**Why LLMs need this:** Overwriting entire files is risky and token-expensive. This tool allows the LLM to replace the content of a specific semantic block without affecting the rest of the document.

**What it does:** Replaces text in a specific element identified by its path.

**Parameters:**
- `file_path` (required): Path to the file
- `path` (required): Semantic path (e.g., "Intro > paragraph 1")
- `new_content` (required): New text for the block

**Example:**
```json
{"file_path": "readme.md", "path": "Installation > paragraph 1", "new_content": "Just run pip install."}
```
</details>

<details>
<summary><b>insert_element</b> - Add new content</summary>

**Why LLMs need this:** Adding new paragraphs, headings, or lists requires understanding document structure. This tool inserts new elements at the right location.

**What it does:** Inserts a new block (heading, paragraph, list, code block, or blockquote) before or after an existing element.

**Parameters:**
- `file_path` (required): Path to the file
- `path` (required): Reference element path
- `element_type` (required): Type (heading, paragraph, list, code_block, blockquote)
- `content` (required): Content of the new element
- `where`: "before" or "after" (default: "after")
- `heading_level`: Level for headings (default: 1)

**Example:**
```json
{"file_path": "doc.md", "path": "Introduction", "element_type": "paragraph", "content": "New paragraph here."}
```
</details>

<details>
<summary><b>delete_element</b> - Remove content</summary>

**Why LLMs need this:** Removing specific blocks without affecting surrounding content requires precision. This tool deletes elements by their semantic path.

**What it does:** Removes a block from the document.

**Parameters:**
- `file_path` (required): Path to the file
- `path` (required): Semantic path to the element to delete

**Example:**
```json
{"file_path": "draft.md", "path": "Old Section"}
```
</details>

<details>
<summary><b>move_element</b> - Structural refactoring</summary>

**Why LLMs need this:** Reorganizing a document is complex. This tool lets the LLM move entire sections (including all nested sub-elements) to a new location with a single command.

**What it does:** Moves a block of text from source path to target path.

**Parameters:**
- `file_path` (required): Path to the file
- `source_path` (required): Path of element to move
- `target_path` (required): Reference path for new location
- `where`: "before" or "after" the target (default: "after")

**Example:**
```json
{"file_path": "draft.md", "source_path": "Contacts", "target_path": "Conclusion"}
```
</details>

<details>
<summary><b>get_context</b> - Context-aware editing</summary>

**Why LLMs need this:** When editing a single block, LLMs might lose the narrative flow. This tool provides the target element along with its immediate neighbors (before and after).

**What it does:** Fetches an element and snippets of surrounding blocks.

**Parameters:**
- `file_path` (required): Path to the file
- `path` (required): Path to the target element

**Example:**
```json
{"file_path": "article.md", "path": "Body > paragraph 5"}
```
</details>

<details>
<summary><b>update_metadata</b> - YAML Frontmatter management</summary>

**Why LLMs need this:** Many Markdown tools (Obsidian, Jekyll) use YAML metadata at the top. This tool allows the LLM to manage tags, dates, and properties without messing with the body text.

**What it does:** Updates or adds YAML Frontmatter to the document.

**Parameters:**
- `file_path` (required): Path to the file
- `metadata` (required): Dictionary of metadata items

**Example:**
```json
{"file_path": "post.md", "metadata": {"status": "published", "tags": ["mcp", "ai"]}}
```
</details>

<details>
<summary><b>undo</b> - Revert changes</summary>

**Why LLMs need this:** Mistakes happen. This tool allows reverting recent operations without manual file restoration.

**What it does:** Reverts the last N operations on the document.

**Parameters:**
- `file_path` (required): Path to the file
- `count`: Number of operations to undo (default: 1)

**Example:**
```json
{"file_path": "document.md", "count": 2}
```
</details>

### File Operations

<details>
<summary><b>list_directory</b> - Explore workspace</summary>

**What it does:** Lists files and folders in a directory, helping the LLM explore the file structure.

**Parameters:**
- `path`: Directory path (default: ".")
</details>

<details>
<summary><b>create_file</b> - Create new document</summary>

**What it does:** Creates a new file with optional initial content.

**Parameters:**
- `path` (required): Path to the new file
- `content`: Initial content (default: "")

**Example:**
```json
{"path": "./notes/todo.md", "content": "# TODO\n\n- Task 1"}
```
</details>

<details>
<summary><b>create_directory</b> - Create folder</summary>

**What it does:** Creates a new directory.

**Parameters:**
- `path` (required): Path to the new directory

**Example:**
```json
{"path": "./docs/archive"}
```
</details>

<details>
<summary><b>delete_item</b> - Cleanup</summary>

**What it does:** Deletes a file or directory.
</details>

## Development

```bash
# Install for development
pip install -e .

# Run tests
pytest tests/
```

### MCP 2025 Standard Features

This server implements all 2025 MCP improvements:

- **Tool Search Tool** - Efficiently find the right tool among many options
- **Tool Use Examples** - Input parameter examples help LLMs use tools correctly
- **Output Schemas** - Structured output definitions for better client integration
- **Dynamic Capabilities** - Support for `tools/list_changed` notifications

---

If you like this project, please give it a star ⭐

[Artem KK](https://www.linkedin.com/in/kazkozdev/) | MIT [LICENSE](LICENSE)
