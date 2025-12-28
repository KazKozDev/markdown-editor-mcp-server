# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.7] - 2024-12-28

### Fixed
- **Critical serialization bugfix**: Fixed `Object of type TextContent is not JSON serializable` error. The `call_tool` function was returning `dict` instead of `mcp.types.CallToolResult`, causing MCP SDK to fail when serializing responses containing `TextContent` objects.

## [0.1.6] - 2024-12-28

### Fixed
- **Critical bugfix**: Read-only tools now return actual data in `TextContent.text`. Previously, `list_directory`, `get_document_structure`, `search_text`, `get_context`, and `read_element` returned only static messages (e.g., "Structure extracted") instead of the actual JSON data. Agents could not "see" the results of these queries, making them effectively blind.

## [0.1.5] - 2024-12-28

### Changed
- Removed incompatible Smithery Build GitHub Actions workflow (container runtime projects deploy via Smithery web interface, not CLI)
- Updated `smithery.yaml` to modern container runtime format
- Added `.dockerignore` for optimized Docker builds

### Fixed
- Clarified Smithery deployment method in documentation (web-based deployment for container runtime)

## [0.1.4] - 2024-12-27

### Added
- Integrated with Smithery.ai for automated deployment.
- Added `smithery.yaml` and `Dockerfile`.
- Configured GitHub Secrets for Smithery API.

## [0.1.3] - 2024-12-27

### Added
- Added PyPI metadata (keywords, classifiers, project URLs) for better discoverability.
- Enhanced package description and documentation references.

## [0.1.2] - 2024-12-27

### Fixed
- Fixed Windows compatibility issues by making `fcntl` usage optional.

## [0.1.1] - 2024-12-27

### Fixed
- Fixed critical bug in Markdown parser where heading nesting was incorrect (siblings became children).
- Fixed `PathResolver` to correctly handle `None` base path in initialization.

### Added
- Comprehensive integration tests with Ollama (`tests/test_ollama_tools.py`).
- Interactive CLI editor script (`interactive_editor.py`) for demonstrating agent capabilities.

## [0.1.0] - 2024-12-26

### Added
- Initial release of the Markdown Editor MCP Server.
- Semantic editing tools: `get_document_structure`, `read_element`, `replace_content`, `insert_element`, `delete_element`.
- Narrative flow tools: `get_context`, `move_element`.
- Information retrieval: `search_text`.
- Metadata management: YAML Frontmatter support via `update_metadata`.
- File system operations: `list_directory`, `create_file`, `create_directory`, `delete_item`.
- Robust Markdown parser with structural element tracking.
- Transaction support (internal logic) and change journaling.
