"""
Markdown parser to structural tree with addressing.
"""

import re
from typing import List, Optional
from .models import Element, ElementType


class MarkdownParser:
    """Markdown parser to structural tree."""

    def parse(self, content: str) -> Element:
        """Parses Markdown and returns structured tree."""
        root = Element(
            type=ElementType.DOCUMENT,
            content=content,
            path="",
            start_pos=0,
            end_pos=len(content),
        )

        lines = content.split("\n")
        current_pos = 0
        elements = []

        i = 0
        while i < len(lines):
            line = lines[i]
            line_start = current_pos
            line_end = current_pos + len(line)

            # Heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                elements.append(
                    Element(
                        type=ElementType.HEADING,
                        content=text,
                        path="",  # Will fill later
                        start_pos=line_start,
                        end_pos=line_end,
                        level=level,
                    )
                )
                current_pos = line_end + 1
                i += 1
                continue

            # Code block
            if line.startswith("```"):
                code_start = line_start
                code_lines = [line]
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    code_lines.append(lines[i])
                    i += 1
                code_content = "\n".join(code_lines)
                code_end = code_start + len(code_content)
                elements.append(
                    Element(
                        type=ElementType.CODE,
                        content=code_content,
                        path="",
                        start_pos=code_start,
                        end_pos=code_end,
                    )
                )
                current_pos = code_end + 1
                continue

            # List (simple)
            if re.match(r"^[\-\*\+]\s+", line) or re.match(r"^\d+\.\s+", line):
                list_start = line_start
                list_lines = []
                while i < len(lines) and (
                    re.match(r"^[\-\*\+]\s+", lines[i])
                    or re.match(r"^\d+\.\s+", lines[i])
                    or (lines[i].startswith("  ") and list_lines)
                ):
                    list_lines.append(lines[i])
                    i += 1
                list_content = "\n".join(list_lines)
                list_end = list_start + len(list_content)
                elements.append(
                    Element(
                        type=ElementType.LIST,
                        content=list_content,
                        path="",
                        start_pos=list_start,
                        end_pos=list_end,
                    )
                )
                current_pos = list_end + 1
                continue

            # Blockquote
            if line.startswith(">"):
                quote_start = line_start
                quote_lines = []
                while i < len(lines) and (
                    lines[i].startswith(">") or lines[i].strip() == ""
                ):
                    if (
                        lines[i].strip() == ""
                        and quote_lines
                        and not quote_lines[-1].startswith(">")
                    ):
                        break
                    quote_lines.append(lines[i])
                    i += 1
                quote_content = "\n".join(quote_lines).rstrip()
                quote_end = quote_start + len(quote_content)
                elements.append(
                    Element(
                        type=ElementType.BLOCKQUOTE,
                        content=quote_content,
                        path="",
                        start_pos=quote_start,
                        end_pos=quote_end,
                    )
                )
                current_pos = quote_end + 1
                continue

            # Thematic break
            if re.match(r"^[\-\*_]{3,}\s*$", line):
                elements.append(
                    Element(
                        type=ElementType.THEMATIC_BREAK,
                        content=line,
                        path="",
                        start_pos=line_start,
                        end_pos=line_end,
                    )
                )
                current_pos = line_end + 1
                i += 1
                continue

            # Empty line — skip
            if line.strip() == "":
                current_pos = line_end + 1
                i += 1
                continue

            # Paragraph
            para_start = line_start
            para_lines = [line]
            i += 1
            while (
                i < len(lines)
                and lines[i].strip() != ""
                and not self._is_special_line(lines[i])
            ):
                para_lines.append(lines[i])
                i += 1
            para_content = "\n".join(para_lines)
            para_end = para_start + len(para_content)
            elements.append(
                Element(
                    type=ElementType.PARAGRAPH,
                    content=para_content,
                    path="",
                    start_pos=para_start,
                    end_pos=para_end,
                )
            )
            current_pos = para_end + 1

        # Build structure with paths
        root.children = self._build_hierarchy(elements)
        self._assign_paths(root)

        return root

    def _is_special_line(self, line: str) -> bool:
        """Checks if line is a start of a special block."""
        if re.match(r"^#{1,6}\s+", line):
            return True
        if line.startswith("```"):
            return True
        if re.match(r"^[\-\*\+]\s+", line):
            return True
        if re.match(r"^\d+\.\s+", line):
            return True
        if line.startswith(">"):
            return True
        if re.match(r"^[\-\*_]{3,}\s*$", line):
            return True
        return False

    def _build_hierarchy(self, elements: List[Element]) -> List[Element]:
        """Builds hierarchy based on headings."""
        if not elements:
            return []

        result = []
        stack = []  # (level, element)

        for elem in elements:
            if elem.type == ElementType.HEADING:
                # Find parent in stack
                while stack and stack[-1][0] >= elem.level:
                    stack.pop()

                if stack:
                    stack[-1][1].children.append(elem)
                else:
                    result.append(elem)

                stack.append((elem.level, elem))
            else:
                # Non-heading goes to last heading or root
                if stack:
                    stack[-1][1].children.append(elem)
                else:
                    result.append(elem)

        return result

    def _assign_paths(self, element: Element, parent_path: str = ""):
        """Assigns paths to all elements."""
        type_counters = {}

        for child in element.children:
            type_name = self._get_type_name(child.type)

            if child.type == ElementType.HEADING:
                # For headings use their text
                child.path = (
                    child.content
                    if not parent_path
                    else f"{parent_path} > {child.content}"
                )
            else:
                # For others — type + number
                if type_name not in type_counters:
                    type_counters[type_name] = 0
                type_counters[type_name] += 1

                path_name = f"{type_name} {type_counters[type_name]}"
                child.path = (
                    path_name if not parent_path else f"{parent_path} > {path_name}"
                )

            # Recursively for children
            self._assign_paths(child, child.path)

    def _get_type_name(self, elem_type: ElementType) -> str:
        """Returns human-readable type name."""
        names = {
            ElementType.PARAGRAPH: "paragraph",
            ElementType.LIST: "list",
            ElementType.CODE: "code",
            ElementType.BLOCKQUOTE: "blockquote",
            ElementType.THEMATIC_BREAK: "break",
            ElementType.HEADING: "heading",
        }
        return names.get(elem_type, elem_type.value)


def find_element_by_path(root: Element, path: str) -> Optional[Element]:
    """Finds element by structural path."""
    if not path:
        return root

    # Normalize path
    path = path.strip()

    def search(element: Element) -> Optional[Element]:
        if element.path == path:
            return element
        for child in element.children:
            result = search(child)
            if result:
                return result
        return None

    return search(root)


def find_elements_by_partial_path(root: Element, partial_path: str) -> List[Element]:
    """Finds all elements whose path contains specified substring."""
    results = []
    partial_lower = partial_path.lower()

    def search(element: Element):
        if partial_lower in element.path.lower():
            results.append(element)
        for child in element.children:
            search(child)

    search(root)
    return results


def get_all_paths(root: Element) -> List[str]:
    """Returns list of all paths in the document."""
    paths = []

    def collect(element: Element):
        if element.path:
            paths.append(element.path)
        for child in element.children:
            collect(child)

    collect(root)
    return paths
