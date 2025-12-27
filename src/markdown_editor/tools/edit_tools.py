import logging
import os
import fcntl
import tempfile
from typing import Dict, Any, List, Optional
from ..core.document import Document
from ..core.path_utils import resolve_path

logger = logging.getLogger(__name__)


class CachedDocument:
    """Wrapper for Document with cache invalidation support"""

    def __init__(self, document: Document, mtime: float):
        self.document = document
        self.mtime = mtime  # File modification time when loaded


class FileLock:
    """Context manager for file locking"""

    def __init__(self, file_path: str, exclusive: bool = True):
        self.file_path = file_path
        self.exclusive = exclusive
        self.lock_file = None
        self.lock_path = f"{file_path}.lock"

    def __enter__(self):
        # Create lock file if it doesn't exist
        self.lock_file = open(self.lock_path, "w")
        if self.exclusive:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
        else:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_SH)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            # Clean up lock file
            try:
                os.remove(self.lock_path)
            except OSError:
                pass  # Ignore if already removed
        return False


class EditTool:
    """Tool for working with document content"""

    def __init__(self):
        self._documents: Dict[str, CachedDocument] = {}

    def _get_file_mtime(self, file_path: str) -> float:
        """Get file modification time"""
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return 0.0

    def _is_cache_valid(self, abs_path: str) -> bool:
        """Check if cached document is still valid"""
        if abs_path not in self._documents:
            return False

        cached = self._documents[abs_path]
        current_mtime = self._get_file_mtime(abs_path)

        # Cache is valid if file hasn't been modified
        return cached.mtime == current_mtime

    def invalidate_cache(self, file_path: str) -> None:
        """Invalidate cache for a specific file"""
        abs_path = resolve_path(file_path)
        if abs_path in self._documents:
            del self._documents[abs_path]

    def invalidate_all_cache(self) -> None:
        """Invalidate all cached documents"""
        self._documents.clear()

    def get_doc(self, file_path: str) -> Document:
        """Get or load document by path with cache validation"""
        # Use centralized path resolution
        abs_path = resolve_path(file_path)

        # Check if cache is still valid
        if not self._is_cache_valid(abs_path):
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                mtime = self._get_file_mtime(abs_path)
                self._documents[abs_path] = CachedDocument(
                    document=Document(content=content), mtime=mtime
                )
            else:
                self._documents[abs_path] = CachedDocument(
                    document=Document(content=""), mtime=0.0
                )

        return self._documents[abs_path].document

    def _update_cache_mtime(self, abs_path: str) -> None:
        """Update cache mtime after writing file"""
        if abs_path in self._documents:
            self._documents[abs_path].mtime = self._get_file_mtime(abs_path)

    def _atomic_write(self, file_path: str, content: str) -> None:
        """Write file atomically using temp file + rename"""
        abs_path = resolve_path(file_path)
        dir_path = os.path.dirname(abs_path)

        # Write to temp file first
        fd, temp_path = tempfile.mkstemp(dir=dir_path, prefix=".tmp_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            # Atomic rename
            os.replace(temp_path, abs_path)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    async def get_structure(
        self, file_path: str, depth: Optional[int] = None
    ) -> List[dict]:
        doc = self.get_doc(file_path)
        return doc.get_structure(depth=depth)

    async def read(self, file_path: str, path: str) -> Dict[str, Any]:
        doc = self.get_doc(file_path)
        return doc.view_element(path)

    async def replace(
        self, file_path: str, path: str, new_content: str
    ) -> Dict[str, Any]:
        abs_path = resolve_path(file_path)
        with FileLock(abs_path):
            doc = self.get_doc(file_path)
            result = doc.replace(path, new_content)
            if "success" in result:
                try:
                    self._atomic_write(file_path, doc.get_content())
                    self._update_cache_mtime(abs_path)
                    # Confirm journal only after successful file write
                    doc.confirm_journal()
                except Exception as e:
                    # Rollback journal entry on write failure
                    doc.rollback_last_entry()
                    self.invalidate_cache(file_path)
                    return {"error": f"Failed to write file: {e}"}
            # Remove internal field from result
            result.pop("_pending_entry", None)
        return result

    async def insert(
        self,
        file_path: str,
        path: str,
        element_type: str,
        content: str,
        where: str = "after",
        heading_level: int = 1,
    ) -> Dict[str, Any]:
        abs_path = resolve_path(file_path)
        with FileLock(abs_path):
            doc = self.get_doc(file_path)
            if where == "before":
                result = doc.insert_before(path, element_type, content, heading_level)
            else:
                result = doc.insert_after(path, element_type, content, heading_level)
            if "success" in result:
                try:
                    self._atomic_write(file_path, doc.get_content())
                    self._update_cache_mtime(abs_path)
                    doc.confirm_journal()
                except Exception as e:
                    doc.rollback_last_entry()
                    self.invalidate_cache(file_path)
                    return {"error": f"Failed to write file: {e}"}
        return result

    async def delete(self, file_path: str, path: str) -> Dict[str, Any]:
        abs_path = resolve_path(file_path)
        with FileLock(abs_path):
            doc = self.get_doc(file_path)
            result = doc.delete(path)
            if "success" in result:
                try:
                    self._atomic_write(file_path, doc.get_content())
                    self._update_cache_mtime(abs_path)
                    doc.confirm_journal()
                except Exception as e:
                    doc.rollback_last_entry()
                    self.invalidate_cache(file_path)
                    return {"error": f"Failed to write file: {e}"}
        return result

    async def undo(self, file_path: str, count: int = 1) -> Dict[str, Any]:
        abs_path = resolve_path(file_path)
        with FileLock(abs_path):
            doc = self.get_doc(file_path)
            result = doc.undo(count)
            if "success" in result:
                try:
                    self._atomic_write(file_path, doc.get_content())
                    self._update_cache_mtime(abs_path)
                    doc.confirm_journal()
                except Exception as e:
                    self.invalidate_cache(file_path)
                    return {"error": f"Failed to write file: {e}"}
        return result

    async def search(self, file_path: str, query: str) -> List[Dict[str, Any]]:
        doc = self.get_doc(file_path)
        return doc.search_text(query)

    async def get_context(self, file_path: str, path: str) -> Dict[str, Any]:
        doc = self.get_doc(file_path)
        return doc.get_context(path)

    async def move(
        self, file_path: str, src_path: str, dst_path: str, where: str = "after"
    ) -> Dict[str, Any]:
        abs_path = resolve_path(file_path)
        with FileLock(abs_path):
            doc = self.get_doc(file_path)
            result = doc.move_element(src_path, dst_path, where)
            if "success" in result:
                try:
                    self._atomic_write(file_path, doc.get_content())
                    self._update_cache_mtime(abs_path)
                    doc.confirm_journal()
                except Exception as e:
                    self.invalidate_cache(file_path)
                    return {"error": f"Failed to write file: {e}"}
        return result

    async def update_metadata(
        self, file_path: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        abs_path = resolve_path(file_path)
        with FileLock(abs_path):
            doc = self.get_doc(file_path)
            result = doc.update_metadata(metadata)
            if "success" in result:
                try:
                    self._atomic_write(file_path, doc.get_content())
                    self._update_cache_mtime(abs_path)
                    doc.confirm_journal()
                except Exception as e:
                    doc.rollback_last_entry()
                    self.invalidate_cache(file_path)
                    return {"error": f"Failed to write file: {e}"}
        return result


# Global instance following the template
_instance = EditTool()


# Async wrappers following the template
async def get_document_structure(file_path: str, depth: Optional[int] = None):
    return await _instance.get_structure(file_path, depth)


async def read_element(file_path: str, path: str):
    return await _instance.read(file_path, path)


async def replace_content(file_path: str, path: str, new_content: str):
    return await _instance.replace(file_path, path, new_content)


async def insert_element(
    file_path: str,
    path: str,
    element_type: str,
    content: str,
    where: str = "after",
    heading_level: int = 1,
):
    return await _instance.insert(
        file_path, path, element_type, content, where, heading_level
    )


async def delete_element(file_path: str, path: str):
    return await _instance.delete(file_path, path)


async def undo_changes(file_path: str, count: int = 1):
    return await _instance.undo(file_path, count)


async def search_in_document(file_path: str, query: str):
    return await _instance.search(file_path, query)


async def get_element_context(file_path: str, path: str):
    return await _instance.get_context(file_path, path)


async def move_document_element(
    file_path: str, src_path: str, dst_path: str, where: str = "after"
):
    return await _instance.move(file_path, src_path, dst_path, where)


async def update_document_metadata(file_path: str, metadata: Dict[str, Any]):
    return await _instance.update_metadata(file_path, metadata)
