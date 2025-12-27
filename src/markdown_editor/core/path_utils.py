"""
Unified path resolution utilities for markdown-editor-mcp-server.

This module provides consistent path handling across all tools to prevent
path resolution conflicts between EditTool and FileOperationsTool.
"""

import os
from typing import Optional


class PathResolver:
    """
    Centralized path resolver for consistent path handling.

    All tools should use this class to resolve file paths, ensuring
    consistent behavior regardless of the tool being used.
    """

    _instance: Optional["PathResolver"] = None
    _base_path: str = "."

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._base_path = os.getcwd()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "PathResolver":
        """Get singleton instance"""
        return cls()

    @classmethod
    def set_base_path(cls, path: Optional[str]) -> None:
        """Set base path for relative path resolution"""
        instance = cls.get_instance()
        if path is None:
            instance._base_path = os.getcwd()
        else:
            instance._base_path = os.path.abspath(path)

    @classmethod
    def get_base_path(cls) -> str:
        """Get current base path"""
        instance = cls.get_instance()
        return instance._base_path

    @classmethod
    def resolve(cls, path: str) -> str:
        """
        Resolve a path to an absolute path.

        Rules:
        1. If path is already absolute, return it as-is
        2. If path is relative, resolve relative to base_path (not cwd)

        This ensures consistent behavior regardless of current working directory.

        Args:
            path: File path (absolute or relative)

        Returns:
            Absolute path
        """
        if os.path.isabs(path):
            return os.path.normpath(path)

        instance = cls.get_instance()
        return os.path.normpath(os.path.join(instance._base_path, path))

    @classmethod
    def is_safe_path(cls, path: str) -> bool:
        """
        Check if path is safe (no path traversal attacks).

        A path is considered safe if the resolved absolute path
        is within or equal to the base path.

        Args:
            path: File path to check

        Returns:
            True if path is safe, False otherwise
        """
        instance = cls.get_instance()
        abs_path = cls.resolve(path)
        base_path = instance._base_path

        # Normalize both paths for comparison
        abs_path = os.path.normpath(abs_path)
        base_path = os.path.normpath(base_path)

        # Check if resolved path is within base path
        # Use os.path.commonpath to handle edge cases
        try:
            common = os.path.commonpath([abs_path, base_path])
            return common == base_path
        except ValueError:
            # Different drives on Windows
            return False

    @classmethod
    def relative_to_base(cls, path: str) -> str:
        """
        Get path relative to base path.

        Args:
            path: Absolute or relative path

        Returns:
            Path relative to base path
        """
        abs_path = cls.resolve(path)
        instance = cls.get_instance()
        return os.path.relpath(abs_path, instance._base_path)


# Convenience functions for direct import
def resolve_path(path: str) -> str:
    """Resolve path to absolute path"""
    return PathResolver.resolve(path)


def is_safe_path(path: str) -> bool:
    """Check if path is safe from traversal attacks"""
    return PathResolver.is_safe_path(path)


def set_base_path(path: str) -> None:
    """Set base path for relative path resolution"""
    PathResolver.set_base_path(path)


def get_base_path() -> str:
    """Get current base path"""
    return PathResolver.get_base_path()
