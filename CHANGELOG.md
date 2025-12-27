# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
