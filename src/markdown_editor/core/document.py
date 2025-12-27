"""
Document model: Markdown parsing, structural tree, element addressing.
"""

import re
import json
import yaml
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from copy import deepcopy
from pathlib import Path


import uuid


def _generate_element_id() -> str:
    """Generate a unique element ID"""
    return uuid.uuid4().hex[:8]


@dataclass
class Element:
    """Document element"""
    type: str  # heading, paragraph, list, code_block, blockquote, list_item
    content: str
    level: int = 0  # for headings (1-6), for lists (nesting depth)
    start_pos: int = 0  # position in original text
    end_pos: int = 0
    children: List["Element"] = field(default_factory=list)
    parent: Optional["Element"] = None

    # Unique stable ID for the element
    element_id: str = field(default_factory=_generate_element_id)

    # Calculated path
    _path: Optional[str] = field(default=None, repr=False)
    
    @property
    def path(self) -> str:
        """Return path to element"""
        if self._path:
            return self._path
        return self._compute_path()
    
    def _compute_path(self) -> str:
        """Calculate path based on tree position"""
        parts = []
        current = self
        
        while current:
            if current.type == "heading":
                # Heading — use its text
                parts.insert(0, current.content.strip()[:50])
            elif current.type == "paragraph":
                # Paragraph — search for index among siblings
                if current.parent:
                    siblings = [c for c in current.parent.children if c.type == "paragraph"]
                    idx = siblings.index(current) + 1
                    parts.insert(0, f"paragraph {idx}")
                else:
                    parts.insert(0, "paragraph")
            elif current.type == "list":
                if current.parent:
                    siblings = [c for c in current.parent.children if c.type == "list"]
                    idx = siblings.index(current) + 1
                    parts.insert(0, f"list {idx}")
            elif current.type == "list_item":
                if current.parent:
                    idx = current.parent.children.index(current) + 1
                    parts.insert(0, f"item {idx}")
            elif current.type == "code_block":
                if current.parent:
                    siblings = [c for c in current.parent.children if c.type == "code_block"]
                    idx = siblings.index(current) + 1
                    parts.insert(0, f"code {idx}")
            elif current.type == "blockquote":
                if current.parent:
                    siblings = [c for c in current.parent.children if c.type == "blockquote"]
                    idx = siblings.index(current) + 1
                    parts.insert(0, f"quote {idx}")
            
            current = current.parent
        
        return " > ".join(parts) if parts else "root"
    
    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            "type": self.type,
            "content": self.content,
            "level": self.level,
            "path": self.path,
            "children": [c.to_dict() for c in self.children]
        }


@dataclass
class JournalEntry:
    """Entry in the change journal"""
    operation: str  # replace, insert, delete, move, update_metadata
    path: str
    old_value: Optional[str]
    new_value: Optional[str]
    timestamp: datetime = field(default_factory=datetime.now)
    transaction_id: Optional[str] = None
    # Additional data for complex undo operations
    element_type: Optional[str] = None  # For insert/delete: type of element
    element_level: int = 0  # For headings
    parent_path: Optional[str] = None  # Parent element path for restoring position
    sibling_index: int = 0  # Index among siblings for exact position restoration
    where: Optional[str] = None  # "before" or "after" for insert operations
    # Stable element IDs for reliable undo
    element_id: Optional[str] = None  # ID of the affected element
    parent_id: Optional[str] = None  # ID of parent element (more reliable than parent_path)

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "path": self.path,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat(),
            "transaction_id": self.transaction_id,
            "element_type": self.element_type,
            "element_level": self.element_level,
            "parent_path": self.parent_path,
            "sibling_index": self.sibling_index,
            "where": self.where,
            "element_id": self.element_id,
            "parent_id": self.parent_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JournalEntry":
        return cls(
            operation=data["operation"],
            path=data["path"],
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            transaction_id=data.get("transaction_id"),
            element_type=data.get("element_type"),
            element_level=data.get("element_level", 0),
            parent_path=data.get("parent_path"),
            sibling_index=data.get("sibling_index", 0),
            where=data.get("where"),
            element_id=data.get("element_id"),
            parent_id=data.get("parent_id")
        )


class MarkdownParser:
    """
    Simple Markdown parser to structural tree.
    Zero external dependencies for core functionality.
    """
    
    def parse(self, text: str) -> Tuple[Dict[str, Any], List[Element]]:
        """Parse Markdown into metadata and element list"""
        metadata = {}
        content = text
        
        # YAML Frontmatter processing
        if text.startswith('---'):
            parts = re.split(r'^---', text, maxsplit=2, flags=re.MULTILINE)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                    content = parts[2].strip()
                except Exception:
                    content = text

        lines = content.split('\n')
        elements = []
        current_section = None
        i = 0
        pos = 0
        
        while i < len(lines):
            line = lines[i]
            line_start = pos
            
            # Heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2)
                
                element = Element(
                    type="heading",
                    content=content,
                    level=level,
                    start_pos=line_start,
                    end_pos=line_start + len(line)
                )
                
                # Determine parent based on level
                # Walk up the tree to find the correct parent
                parent = current_section
                while parent and parent.level >= level:
                    parent = parent.parent
                
                if parent:
                    element.parent = parent
                    parent.children.append(element)
                else:
                    elements.append(element)
                
                current_section = element
                pos += len(line) + 1
                i += 1
                continue
            
            # Code block
            if line.startswith('```'):
                code_lines = [line]
                _ = line[3:].strip()  # lang - not used but preserved for future
                i += 1
                pos += len(line) + 1
                _ = pos  # code_start - not used but preserved for future
                
                while i < len(lines) and not lines[i].startswith('```'):
                    code_lines.append(lines[i])
                    pos += len(lines[i]) + 1
                    i += 1
                
                if i < len(lines):
                    code_lines.append(lines[i])
                    pos += len(lines[i]) + 1
                    i += 1
                
                element = Element(
                    type="code_block",
                    content='\n'.join(code_lines[1:-1]) if len(code_lines) > 2 else "",
                    level=0,
                    start_pos=line_start,
                    end_pos=pos - 1
                )
                
                if current_section:
                    element.parent = current_section
                    current_section.children.append(element)
                else:
                    elements.append(element)
                continue
            
            # Blockquote
            if line.startswith('>'):
                quote_lines = []
                quote_start = line_start
                
                while i < len(lines) and (lines[i].startswith('>') or (lines[i].strip() == '' and i + 1 < len(lines) and lines[i + 1].startswith('>'))):
                    quote_lines.append(lines[i].lstrip('> '))
                    pos += len(lines[i]) + 1
                    i += 1
                
                element = Element(
                    type="blockquote",
                    content='\n'.join(quote_lines),
                    start_pos=quote_start,
                    end_pos=pos - 1
                )
                
                if current_section:
                    element.parent = current_section
                    current_section.children.append(element)
                else:
                    elements.append(element)
                continue
            
            # List
            list_match = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.+)$', line)
            if list_match:
                list_items = []
                list_start = line_start
                
                while i < len(lines):
                    item_match = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.+)$', lines[i])
                    if item_match:
                        indent = len(item_match.group(1))
                        content = item_match.group(3)
                        list_items.append(Element(
                            type="list_item",
                            content=content,
                            level=indent // 2,
                            start_pos=pos,
                            end_pos=pos + len(lines[i])
                        ))
                        pos += len(lines[i]) + 1
                        i += 1
                    elif lines[i].strip() == '':
                        pos += len(lines[i]) + 1
                        i += 1
                        # Check if list continues
                        if i < len(lines) and re.match(r'^(\s*)([-*+]|\d+\.)\s+', lines[i]):
                            continue
                        break
                    else:
                        break
                
                element = Element(
                    type="list",
                    content="",
                    start_pos=list_start,
                    end_pos=pos - 1,
                    children=list_items
                )
                
                # Set parent for items
                for item in list_items:
                    item.parent = element
                
                if current_section:
                    element.parent = current_section
                    current_section.children.append(element)
                else:
                    elements.append(element)
                continue
            
            # Empty line
            if line.strip() == '':
                pos += len(line) + 1
                i += 1
                continue
            
            # Normal paragraph
            para_lines = []
            para_start = line_start
            
            while i < len(lines) and lines[i].strip() != '' and not lines[i].startswith('#') and not lines[i].startswith('```') and not lines[i].startswith('>') and not re.match(r'^(\s*)([-*+]|\d+\.)\s+', lines[i]):
                para_lines.append(lines[i])
                pos += len(lines[i]) + 1
                i += 1
            
            if para_lines:
                element = Element(
                    type="paragraph",
                    content='\n'.join(para_lines),
                    start_pos=para_start,
                    end_pos=pos - 1
                )
                
                if current_section:
                    element.parent = current_section
                    current_section.children.append(element)
                else:
                    elements.append(element)
        
        return metadata, elements
    
    def serialize(self, elements: List[Element], metadata: Optional[Dict[str, Any]] = None) -> str:
        """Serialize tree back to Markdown"""
        lines = []
        
        if metadata:
            lines.append('---')
            lines.append(yaml.dump(metadata, allow_unicode=True).strip())
            lines.append('---')
            lines.append('')

        for element in elements:
            lines.extend(self._serialize_element(element))
        
        return '\n'.join(lines)
    
    def _serialize_element(self, element: Element, indent: int = 0) -> List[str]:
        """Serialize a single element"""
        lines = []
        
        if element.type == "heading":
            lines.append('#' * element.level + ' ' + element.content)
            lines.append('')
            for child in element.children:
                lines.extend(self._serialize_element(child))
        
        elif element.type == "paragraph":
            lines.append(element.content)
            lines.append('')
        
        elif element.type == "code_block":
            lines.append('```')
            lines.append(element.content)
            lines.append('```')
            lines.append('')
        
        elif element.type == "blockquote":
            for line in element.content.split('\n'):
                lines.append('> ' + line)
            lines.append('')
        
        elif element.type == "list":
            for i, item in enumerate(element.children):
                prefix = '  ' * item.level + '- '
                lines.append(prefix + item.content)
            lines.append('')
        
        return lines


class Document:
    """
    Document with support for:
    - Structural view
    - Change journal
    - Transactions
    - Path-based addressing
    """

    def __init__(self, content: str = "", journal_path: Optional[str] = None,
                 file_path: Optional[str] = None):
        self.raw_content = content
        self.parser = MarkdownParser()
        self.elements: List[Element] = []
        self.metadata: Dict[str, Any] = {}
        self.journal: List[JournalEntry] = []
        self.journal_path = journal_path
        self.file_path = file_path  # Path to source file for transaction validation

        # Transaction state
        self._transaction_active = False
        self._transaction_id: Optional[str] = None
        self._snapshot: Optional[Tuple[str, List[Element], Dict[str, Any]]] = None
        self._transaction_file_mtime: Optional[float] = None  # File mtime at transaction start

        # Versioning
        self.version = 0

        if content:
            self.build_structure()

        if journal_path:
            self._load_journal()
    
    def build_structure(self):
        """Rebuild structural tree from raw_content"""
        self.metadata, self.elements = self.parser.parse(self.raw_content)
    
    def _load_journal(self):
        """Load journal from file"""
        if self.journal_path and Path(self.journal_path).exists():
            with open(self.journal_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.journal = [JournalEntry.from_dict(e) for e in data]
    
    def _save_journal(self):
        """Save journal to file"""
        if self.journal_path:
            with open(self.journal_path, 'w', encoding='utf-8') as f:
                json.dump([e.to_dict() for e in self.journal], f, indent=2, ensure_ascii=False)

    def confirm_journal(self) -> None:
        """Confirm journal entries by saving to disk.

        Call this after successful file write to persist journal entries.
        """
        self._save_journal()

    def rollback_last_entry(self) -> None:
        """Remove the last journal entry (for rollback on failed file write).

        Call this if file write fails after a successful document operation.
        """
        if self.journal:
            self.journal.pop()
            self.version = max(0, self.version - 1)
    
    def get_structure(self, depth: Optional[int] = None) -> List[dict]:
        """Get document structure"""
        def element_to_struct(el: Element, current_depth: int = 0) -> dict:
            result = {
                "type": el.type,
                "path": el.path,
                "preview": el.content[:100] + "..." if len(el.content) > 100 else el.content
            }
            if el.level:
                result["level"] = el.level
            
            if el.children and (depth is None or current_depth < depth):
                result["children"] = [element_to_struct(c, current_depth + 1) for c in el.children]
            
            return result
        
        return [element_to_struct(el) for el in self.elements]
    
    def find_by_path(self, path: str, exact: bool = False) -> Optional[Element]:
        """Find element by path

        Args:
            path: Path string like "Heading > paragraph 1" or "Introduction > code 2"
            exact: If True, require exact match. If False, allow fuzzy matching (default).

        Returns:
            Element if found, None otherwise.
        """
        path_parts = [p.strip() for p in path.split('>')]

        def normalize(s: str) -> str:
            """Normalize string for comparison"""
            return s.lower().strip()

        def exact_match(el: Element, target: str) -> bool:
            """Check for exact match"""
            target_norm = normalize(target)
            el_path_part = el.path.split(' > ')[-1] if ' > ' in el.path else el.path

            # For headings, compare with content
            if el.type == "heading":
                return normalize(el.content) == target_norm

            # For other elements, compare path part exactly
            return normalize(el_path_part) == target_norm

        def fuzzy_match(el: Element, target: str) -> bool:
            """Check for fuzzy match with clear rules:
            1. For headings: target must be a prefix of content (case-insensitive)
            2. For indexed elements (paragraph 1, code 2): must match type and index exactly
            """
            target_norm = normalize(target)
            el_path_part = el.path.split(' > ')[-1] if ' > ' in el.path else el.path
            el_path_norm = normalize(el_path_part)

            # For headings: target should be prefix or exact match
            if el.type == "heading":
                content_norm = normalize(el.content)
                # Exact match or content starts with target
                return content_norm == target_norm or content_norm.startswith(target_norm)

            # For indexed elements (paragraph 1, list 2, etc): require exact match
            # This prevents "paragraph 1" from matching "paragraph 10"
            return el_path_norm == target_norm

        def search(elements: List[Element], parts: List[str], depth: int = 0) -> Optional[Element]:
            if not parts:
                return None

            target = parts[0]
            match_func = exact_match if exact else fuzzy_match
            candidates = []

            for el in elements:
                if match_func(el, target):
                    if len(parts) == 1:
                        candidates.append(el)
                    else:
                        # Continue searching in children
                        res = search(el.children, parts[1:], depth + 1)
                        if res:
                            return res

            # Return first candidate if any found at current level
            if candidates:
                if len(candidates) > 1 and not exact:
                    # Multiple matches - prefer exact content match
                    for c in candidates:
                        if c.type == "heading" and normalize(c.content) == normalize(target):
                            return c
                return candidates[0]

            # If not found at current level, search in all children (for nested paths)
            if depth == 0:
                for el in elements:
                    res = search(el.children, parts, depth + 1)
                    if res:
                        return res

            return None

        return search(self.elements, path_parts)

    def find_by_id(self, element_id: str) -> Optional[Element]:
        """Find element by its unique ID"""
        def search(elements: List[Element]) -> Optional[Element]:
            for el in elements:
                if el.element_id == element_id:
                    return el
                result = search(el.children)
                if result:
                    return result
            return None

        return search(self.elements)

    def view_element(self, path: str) -> Dict[str, Any]:
        """View element by path"""
        element = self.find_by_path(path)
        if not element:
            return {"error": f"Element not found: {path}"}
        
        return {
            "type": element.type,
            "path": element.path,
            "content": element.content,
            "level": element.level,
            "children_count": len(element.children)
        }
    
    def replace(self, path: str, new_content: str) -> Dict[str, Any]:
        """Replace element content"""
        element = self.find_by_path(path)
        if not element:
            return {"error": f"Element not found: {path}"}

        old_content = element.content
        element.content = new_content

        # Rebuild raw_content
        self._rebuild_raw_content()

        # Create journal entry (but don't save yet - caller must confirm after file write)
        entry = JournalEntry(
            operation="replace",
            path=path,
            old_value=old_content,
            new_value=new_content,
            transaction_id=self._transaction_id,
            element_id=element.element_id  # Store element ID for reliable undo
        )

        if not self._transaction_active:
            self.journal.append(entry)
            # Note: _save_journal() is NOT called here
            # Caller must call confirm_journal() after successful file write
            self.version += 1

        return {"success": True, "path": path, "old_content": old_content[:50], "_pending_entry": entry}

    def search_text(self, query: str) -> List[Dict[str, Any]]:
        """Search text across all elements"""
        query = query.lower()
        results = []
        
        def walk(elements):
            for el in elements:
                if query in el.content.lower():
                    results.append({
                        "path": el.path,
                        "type": el.type,
                        "preview": el.content[:100]
                    })
                walk(el.children)
        
        walk(self.elements)
        return results

    def get_context(self, path: str) -> Dict[str, Any]:
        """Get element and its neighbors"""
        target = self.find_by_path(path)
        if not target:
            return {"error": "Not found"}
            
        siblings = target.parent.children if target.parent else self.elements
        idx = siblings.index(target)
        
        context = {
            "current": {"path": target.path, "content": target.content},
            "before": None,
            "after": None
        }
        
        if idx > 0:
            context["before"] = {"path": siblings[idx-1].path, "content": siblings[idx-1].content[:200]}
        if idx < len(siblings) - 1:
            context["after"] = {"path": siblings[idx+1].path, "content": siblings[idx+1].content[:200]}
            
        return context

    def move_element(self, src_path: str, dst_path: str, where: str = "after") -> Dict[str, Any]:
        """Move element"""
        src = self.find_by_path(src_path)
        dst = self.find_by_path(dst_path)
        
        if not src or not dst:
            return {"error": "Source or target path not found"}
            
        # Remove from old location
        if src.parent:
            src.parent.children.remove(src)
        else:
            self.elements.remove(src)
            
        # Insert into new one
        if dst.parent:
            siblings = dst.parent.children
            idx = siblings.index(dst)
            if where == "after":
                siblings.insert(idx + 1, src)
            else:
                siblings.insert(idx, src)
            src.parent = dst.parent
        else:
            idx = self.elements.index(dst)
            if where == "after":
                self.elements.insert(idx + 1, src)
            else:
                self.elements.insert(idx, src)
            src.parent = None
            
        self._rebuild_raw_content()
        return {"success": True, "new_path": src.path}

    def update_metadata(self, new_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update YAML metadata"""
        old = deepcopy(self.metadata)
        self.metadata.update(new_metadata)
        self._rebuild_raw_content()

        # Create journal entry for undo support
        entry = JournalEntry(
            operation="update_metadata",
            path="metadata",
            old_value=json.dumps(old, ensure_ascii=False),
            new_value=json.dumps(self.metadata, ensure_ascii=False),
            transaction_id=self._transaction_id
        )

        if not self._transaction_active:
            self.journal.append(entry)
            # Note: _save_journal() is NOT called here
            # Caller must call confirm_journal() after successful file write
            self.version += 1

        return {"success": True, "old": old, "new": self.metadata}
    
    def insert_after(self, path: str, element_type: str, content: str,
                     heading_level: int = 1) -> Dict[str, Any]:
        """Insert element after specified"""
        target = self.find_by_path(path)
        if not target:
            return {"error": f"Element not found: {path}"}

        new_element = Element(
            type=element_type,
            content=content,
            level=heading_level if element_type == "heading" else 0
        )

        # Find position for insertion
        if target.parent:
            siblings = target.parent.children
            idx = siblings.index(target)
            siblings.insert(idx + 1, new_element)
            new_element.parent = target.parent
            parent_path = target.parent.path
            parent_id = target.parent.element_id
            sibling_index = idx + 1
        else:
            idx = self.elements.index(target)
            self.elements.insert(idx + 1, new_element)
            parent_path = None
            parent_id = None
            sibling_index = idx + 1

        self._rebuild_raw_content()

        # Store the new element's path for undo (to find and remove it)
        new_path = new_element.path

        entry = JournalEntry(
            operation="insert_after",
            path=new_path,  # Path of the NEW element (for removal during undo)
            old_value=None,
            new_value=content,
            transaction_id=self._transaction_id,
            element_type=element_type,
            element_level=heading_level if element_type == "heading" else 0,
            parent_path=parent_path,
            sibling_index=sibling_index,
            where="after",
            element_id=new_element.element_id,  # ID of inserted element
            parent_id=parent_id
        )

        if not self._transaction_active:
            self.journal.append(entry)
            # Note: _save_journal() is NOT called here
            # Caller must call confirm_journal() after successful file write
            self.version += 1

        return {"success": True, "new_path": new_path}

    def insert_before(self, path: str, element_type: str, content: str,
                      heading_level: int = 1) -> Dict[str, Any]:
        """Insert element before specified"""
        target = self.find_by_path(path)
        if not target:
            return {"error": f"Element not found: {path}"}

        new_element = Element(
            type=element_type,
            content=content,
            level=heading_level if element_type == "heading" else 0
        )

        if target.parent:
            siblings = target.parent.children
            idx = siblings.index(target)
            siblings.insert(idx, new_element)
            new_element.parent = target.parent
            parent_path = target.parent.path
            parent_id = target.parent.element_id
            sibling_index = idx
        else:
            idx = self.elements.index(target)
            self.elements.insert(idx, new_element)
            parent_path = None
            parent_id = None
            sibling_index = idx

        self._rebuild_raw_content()

        # Store the new element's path for undo (to find and remove it)
        new_path = new_element.path

        entry = JournalEntry(
            operation="insert_before",
            path=new_path,  # Path of the NEW element (for removal during undo)
            old_value=None,
            new_value=content,
            transaction_id=self._transaction_id,
            element_type=element_type,
            element_level=heading_level if element_type == "heading" else 0,
            parent_path=parent_path,
            sibling_index=sibling_index,
            where="before",
            element_id=new_element.element_id,  # ID of inserted element
            parent_id=parent_id
        )

        if not self._transaction_active:
            self.journal.append(entry)
            # Note: _save_journal() is NOT called here
            # Caller must call confirm_journal() after successful file write
            self.version += 1

        return {"success": True, "new_path": new_path}

    def delete(self, path: str) -> Dict[str, Any]:
        """Delete element"""
        target = self.find_by_path(path)
        if not target:
            return {"error": f"Element not found: {path}"}

        old_content = target.content
        element_type = target.type
        element_level = target.level
        element_id = target.element_id

        # Save position info for undo
        if target.parent:
            siblings = target.parent.children
            sibling_index = siblings.index(target)
            parent_path = target.parent.path
            parent_id = target.parent.element_id
            siblings.remove(target)
        else:
            sibling_index = self.elements.index(target)
            parent_path = None
            parent_id = None
            self.elements.remove(target)

        self._rebuild_raw_content()

        entry = JournalEntry(
            operation="delete",
            path=path,
            old_value=old_content,
            new_value=None,
            transaction_id=self._transaction_id,
            element_type=element_type,
            element_level=element_level,
            parent_path=parent_path,
            sibling_index=sibling_index,
            element_id=element_id,  # ID of deleted element (for reference)
            parent_id=parent_id
        )

        if not self._transaction_active:
            self.journal.append(entry)
            # Note: _save_journal() is NOT called here
            # Caller must call confirm_journal() after successful file write
            self.version += 1

        return {"success": True, "deleted_content": old_content[:50]}
    
    def _rebuild_raw_content(self):
        """Rebuild raw_content from element tree"""
        self.raw_content = self.parser.serialize(self.elements, self.metadata)
    
    # === Transactions ===

    def _get_file_mtime(self) -> Optional[float]:
        """Get file modification time if file_path is set"""
        import os
        if self.file_path and os.path.exists(self.file_path):
            try:
                return os.path.getmtime(self.file_path)
            except OSError:
                pass
        return None

    def _check_file_unchanged(self) -> bool:
        """Check if file hasn't been modified since transaction start"""
        if self._transaction_file_mtime is None:
            return True  # No file tracking, assume OK
        current_mtime = self._get_file_mtime()
        if current_mtime is None:
            return True  # File doesn't exist or no tracking
        return current_mtime == self._transaction_file_mtime

    def begin_transaction(self, description: str = "") -> Dict[str, Any]:
        """Begin transaction with file state tracking"""
        if self._transaction_active:
            return {"error": "Transaction already active"}

        self._transaction_active = True
        self._transaction_id = datetime.now().isoformat()
        self._snapshot = (self.raw_content, deepcopy(self.elements), deepcopy(self.metadata))
        self._transaction_file_mtime = self._get_file_mtime()

        return {"success": True, "transaction_id": self._transaction_id}

    def commit(self) -> Dict[str, Any]:
        """Commit transaction with file validation"""
        if not self._transaction_active:
            return {"error": "No active transaction"}

        # Check if file was modified externally during transaction
        if not self._check_file_unchanged():
            return {
                "error": "File was modified externally during transaction. "
                         "Please rollback and reload the document."
            }

        # Validation
        try:
            test_elements = self.parser.parse(self.raw_content)
            if not test_elements and self.raw_content.strip():
                raise ValueError("Document structure is broken")
        except Exception as e:
            return {"error": f"Validation failed: {e}"}

        self._transaction_active = False
        self._snapshot = None
        self._transaction_file_mtime = None
        self.version += 1
        self._save_journal()

        return {"success": True, "new_version": self.version}

    def rollback(self) -> Dict[str, Any]:
        """Rollback transaction"""
        if not self._transaction_active:
            return {"error": "No active transaction"}

        if self._snapshot:
            self.raw_content, self.elements, self.metadata = self._snapshot

        # Remove entries of this transaction from journal
        self.journal = [e for e in self.journal if e.transaction_id != self._transaction_id]

        self._transaction_active = False
        self._transaction_id = None
        self._snapshot = None
        self._transaction_file_mtime = None

        return {"success": True, "message": "Transaction rolled back"}
    
    # === History ===

    def _restore_element_at_position(self, entry: JournalEntry) -> bool:
        """Restore a deleted element at its original position"""
        if not entry.old_value or not entry.element_type:
            return False

        # Create the element with the original ID if available
        new_element = Element(
            type=entry.element_type,
            content=entry.old_value,
            level=entry.element_level
        )
        # Restore original ID if we have it
        if entry.element_id:
            new_element.element_id = entry.element_id

        # Find parent - prefer ID-based lookup, fall back to path
        parent = None
        if entry.parent_id:
            parent = self.find_by_id(entry.parent_id)
        if not parent and entry.parent_path:
            parent = self.find_by_path(entry.parent_path)

        if parent:
            new_element.parent = parent
            # Insert at original index
            idx = min(entry.sibling_index, len(parent.children))
            parent.children.insert(idx, new_element)
            return True
        elif not entry.parent_path and not entry.parent_id:
            # Insert at root level
            idx = min(entry.sibling_index, len(self.elements))
            self.elements.insert(idx, new_element)
            return True

        return False

    def _remove_inserted_element(self, entry: JournalEntry) -> bool:
        """Remove an element that was inserted (for undo of insert operations)"""
        # Prefer ID-based lookup for reliability
        element = None
        if entry.element_id:
            element = self.find_by_id(entry.element_id)
        if not element:
            element = self.find_by_path(entry.path)
        if not element:
            return False

        # Remove from parent or root
        if element.parent:
            if element in element.parent.children:
                element.parent.children.remove(element)
                return True
        else:
            if element in self.elements:
                self.elements.remove(element)
                return True

        return False

    def undo(self, count: int = 1) -> Dict[str, Any]:
        """Undo last operations"""
        if not self.journal:
            return {"error": "Journal is empty"}

        undone = []
        errors = []

        for _ in range(min(count, len(self.journal))):
            entry = self.journal.pop()
            success = False

            # Apply reverse operation
            if entry.operation == "replace":
                # Prefer ID-based lookup for reliability
                element = None
                if entry.element_id:
                    element = self.find_by_id(entry.element_id)
                if not element:
                    element = self.find_by_path(entry.path)

                if element and entry.old_value is not None:
                    element.content = entry.old_value
                    success = True
                else:
                    errors.append(f"Cannot undo replace: element not found at {entry.path}")

            elif entry.operation == "delete":
                # Restore deleted element at its original position
                success = self._restore_element_at_position(entry)
                if not success:
                    errors.append(f"Cannot undo delete: failed to restore element at {entry.path}")

            elif entry.operation in ("insert_after", "insert_before"):
                # Remove the inserted element
                success = self._remove_inserted_element(entry)
                if not success:
                    errors.append(f"Cannot undo {entry.operation}: element not found at {entry.path}")

            elif entry.operation == "update_metadata":
                # Restore old metadata
                if entry.old_value:
                    try:
                        old_metadata = json.loads(entry.old_value)
                        self.metadata = old_metadata
                        success = True
                    except (json.JSONDecodeError, TypeError):
                        errors.append("Cannot undo update_metadata: invalid old value")
                else:
                    errors.append("Cannot undo update_metadata: no old value stored")

            if success:
                undone.append(entry.operation)

        self._rebuild_raw_content()
        self._save_journal()

        result = {"success": True, "undone_operations": undone}
        if errors:
            result["warnings"] = errors

        return result
    
    def get_history(self, limit: int = 10) -> List[dict]:
        """Get change history"""
        return [e.to_dict() for e in self.journal[-limit:]]
    
    def get_content(self) -> str:
        """Get current content"""
        return self.raw_content
