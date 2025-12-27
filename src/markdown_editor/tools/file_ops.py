import os
import shutil
import logging
from typing import List, Dict, Optional, Any
from ..core.path_utils import resolve_path, is_safe_path, get_base_path

logger = logging.getLogger(__name__)


class FileOperationsTool:
    def __init__(self, base_path: Optional[str] = None):
        # Use centralized path resolver - ignore base_path param for consistency
        # The base path should be set globally via PathResolver.set_base_path()
        pass

    def _get_abs_path(self, path: str) -> str:
        """Get absolute path using centralized resolver"""
        return resolve_path(path)

    def _validate_path(self, path: str) -> Optional[str]:
        """Validate path is safe and return error message if not"""
        if not is_safe_path(path):
            return f"Access denied: path '{path}' is outside allowed directory"
        return None

    async def list_directory(self, path: str = ".") -> Optional[List[Dict[str, Any]]]:
        """List files and folders"""
        try:
            # Validate path safety
            error = self._validate_path(path)
            if error:
                logger.error(error)
                return None

            abs_path = self._get_abs_path(path)
            if not os.path.exists(abs_path):
                return None

            base_path = get_base_path()
            items = []
            for entry in os.scandir(abs_path):
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else 0,
                    "path": os.path.relpath(entry.path, base_path)
                })
            return items
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return None

    async def create_directory(self, path: str) -> Dict[str, Any]:
        """Create directory"""
        # Validate path safety
        error = self._validate_path(path)
        if error:
            return {"error": error}

        try:
            abs_path = self._get_abs_path(path)
            os.makedirs(abs_path, exist_ok=True)
            return {"success": True, "path": path}
        except Exception as e:
            return {"error": str(e)}

    async def create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        """Create file"""
        # Validate path safety
        error = self._validate_path(path)
        if error:
            return {"error": error}

        try:
            abs_path = self._get_abs_path(path)
            # Create parent directories if they don't exist
            parent_dir = os.path.dirname(abs_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": path, "size": len(content)}
        except Exception as e:
            return {"error": str(e)}

    async def delete_item(self, path: str) -> Dict[str, Any]:
        """Delete file or directory"""
        # Validate path safety
        error = self._validate_path(path)
        if error:
            return {"error": error}

        try:
            abs_path = self._get_abs_path(path)
            if not os.path.exists(abs_path):
                return {"error": "Item not found"}

            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
            else:
                os.remove(abs_path)
            return {"success": True, "path": path}
        except Exception as e:
            return {"error": str(e)}

# Global instance
_instance = FileOperationsTool()

async def list_directory(path: str = "."):
    return await _instance.list_directory(path)

async def create_directory(path: str):
    return await _instance.create_directory(path)

async def create_file(path: str, content: str = ""):
    return await _instance.create_file(path, content)

async def delete_item(path: str):
    return await _instance.delete_item(path)
